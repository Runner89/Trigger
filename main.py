from flask import Flask, request, jsonify
import time
import hmac
import hashlib
import requests
import urllib.parse

app = Flask(__name__)

BASE_URL = "https://open-api.bingx.com"
ORDER_ENDPOINT = "/openApi/swap/v2/trade/order"

def generate_signature(secret_key: str, params: str) -> str:
    return hmac.new(secret_key.encode(), params.encode(), hashlib.sha256).hexdigest()

def place_trigger_order(api_key, secret_key, symbol, usdt_amount, trigger_price):

    MIN_QTY = 584
    quantity = max(int(usdt_amount / trigger_price), MIN_QTY)

    timestamp = int(time.time() * 1000)

    params_dict = {
        "symbol": symbol,
        "side": "BUY",
        "type": "STOP_MARKET",
        "positionSide": "LONG",
        "quantity": str(quantity),
        "stopPrice": str(trigger_price),
        "workingType": "MARK_PRICE",
        "reduceOnly": "false",
        "timeInForce": "GTC",
        "timestamp": str(timestamp)
    }

    # Query-String alphabetisch sortieren + URL-encoden
    query_string = urllib.parse.urlencode(sorted(params_dict.items()))
    
    # Signatur auf genau diesen Query-String anwenden
    signature = generate_signature(secret_key, query_string)

    # Signatur anhängen
    full_query = query_string + "&signature=" + signature

    url = f"{BASE_URL}{ORDER_ENDPOINT}?{full_query}"

    headers = {"X-BX-APIKEY": api_key}

    # POST ***OHNE JSON BODY***
    response = requests.post(url, headers=headers)

    return response.json()



@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.json

    api_key = "HCMkr3dg22Hepo9iJWEABqptvDmEmsJBOB0Gr5MptJMuk0a8dl4p7zFCOkdpVGb2AcwDwXaCLA2Go4X0h2g"
    secret_key = "xhnk9SG2t8dDxjae7UbUaicE8iQrbrUTUaJ6GZXnxMzsbaT3aabL90EeuqMCBLs5UBiKaTgQRyItWOKjesF0A"
    symbol = "PUMP-USDT"
    trigger_price = float(data.get("trigger_price", 0.0028))
    usdt_amount = float(data.get("usdt_amount", 5))

    order_response = place_trigger_order(api_key, secret_key, symbol, usdt_amount, trigger_price)

    return jsonify({
        "status": "trigger_order_placed",
        "symbol": symbol,
        "trigger_price": trigger_price,
        "usdt_amount": usdt_amount,
        "order_response": order_response
    })


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
