from flask import Flask, request, jsonify
import time
import hmac
import hashlib
import requests

app = Flask(__name__)

BASE_URL = "https://open-api.bingx.com"
ORDER_ENDPOINT = "/openApi/swap/v2/trade/order"

def generate_signature(secret_key: str, params: str) -> str:
    return hmac.new(secret_key.encode(), params.encode(), hashlib.sha256).hexdigest()

def place_trigger_order(api_key, secret_key, symbol, usdt_amount, trigger_price):
    # Menge berechnen und auf ganze Tokens runden
    quantity = int(usdt_amount / trigger_price)
    timestamp = int(time.time() * 1000)

    params_dict = {
        "symbol": symbol,
        "side": "BUY",               # LONG Entry
        "type": "STOP_MARKET",       # Trigger Order
        "quantity": quantity,
        "positionSide": "LONG",
        "reduceOnly": False,         # Entry Order, nicht zum Schließen
        "stopPrice": trigger_price,  # Trigger Price
        "workingType": "MARK_PRICE", # Oder "CONTRACT_PRICE"
        "timestamp": timestamp
    }

    # Signatur erstellen
    query_string = "&".join(f"{k}={params_dict[k]}" for k in sorted(params_dict))
    signature = generate_signature(secret_key, query_string)
    params_dict["signature"] = signature

    url = f"{BASE_URL}{ORDER_ENDPOINT}"
    headers = {"X-BX-APIKEY": api_key, "Content-Type": "application/json"}
    response = requests.post(url, headers=headers, json=params_dict)
    return response.json()

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.json

    api_key = "HCMkr3dg22Hepo9iJWEABqptvDmEmsJBOB0Gr5MptJMuk0a8dl4p7zFCOkdpVGb2AcwDwXaCLA2Go4X0h2g"
    secret_key = "xhnk9SG2t8dDxjae7UbUaicE8iQrbrUTUaJ6GZXnxMzsbaT3aabL90EeuqMCBLs5UBiKaTgQRyItWOKjesF0A"
    symbol = data.get("symbol", "PUMP-USDT")
    trigger_price = float(data.get("trigger_price", 0.0028))
    usdt_amount = float(data.get("usdt_amount", 5))

    if not api_key or not secret_key or not symbol:
        return jsonify({"error": True, "msg": "api_key, secret_key und symbol sind erforderlich"}), 400

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
