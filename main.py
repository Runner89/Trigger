from flask import Flask, request, jsonify
import requests
import time
import hmac
import hashlib

app = Flask(__name__)

BASE_URL = "https://open-api.bingx.com"
ORDER_ENDPOINT = "/openApi/swap/v2/trade/order"

def generate_signature(secret_key: str, params: str) -> str:
    return hmac.new(secret_key.encode('utf-8'), params.encode('utf-8'), hashlib.sha256).hexdigest()

def place_market_order(api_key, secret_key, symbol, usdt_amount, position_side="LONG"):
    # Menge anhand USDT berechnen – optional hier für Market-Order, Preis kann als Info gespeichert werden
    timestamp = int(time.time() * 1000)

    params_dict = {
        "symbol": symbol,
        "side": "BUY",
        "type": "MARKET",
        "quantity": round(usdt_amount, 6),  # Wenn BingX USDT-Menge direkt akzeptiert, sonst Preis / Menge berechnen
        "positionSide": position_side,
        "timestamp": timestamp
    }

    query_string = "&".join(f"{k}={params_dict[k]}" for k in sorted(params_dict))
    signature = generate_signature(secret_key, query_string)
    params_dict["signature"] = signature

    url = f"{BASE_URL}{ORDER_ENDPOINT}"
    headers = {
        "X-BX-APIKEY": api_key,
        "Content-Type": "application/json"
    }

    response = requests.post(url, headers=headers, json=params_dict)
    return response.json()


@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.json
    api_key = "HCMkr3dg22Hepo9iJWEABqptvDmEmsJBOB0Gr5MptJMuk0a8dl4p7zFCOkdpVGb2AcwDwXaCLA2Go4X0h2g"
    secret_key = "xhnk9SG2t8dDxjae7UbUaicE8iQrbrUTUaJ6GZXnxMzsbaT3aabL90EeuqMCBLs5UBiKaTgQRyItWOKjesF0A"
    symbol = "PUMP_USDT"
    
    # Direkt die Order setzen mit festem Trigger-Preis als Info
    trigger_price = 0.002800
    usdt_amount = 5

    order_resp = place_market_order(api_key, secret_key, symbol, usdt_amount, "LONG")
    return jsonify({
        "status": "order_placed",
        "symbol": symbol,
        "trigger_price": trigger_price,
        "usdt_amount": usdt_amount,
        "order_response": order_resp
    })


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
