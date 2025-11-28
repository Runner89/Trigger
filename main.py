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


def place_trigger_market_order(api_key, secret_key, symbol, quantity, trigger_price):
    timestamp = int(time.time() * 1000)

    # Parameter für TRIGGER_MARKET ENTRY ORDER
    params_dict = {
        "symbol": symbol,
        "side": "BUY",
        "type": "TRIGGER_MARKET",
        "positionSide": "LONG",
        "triggerPrice": str(trigger_price),
        "quantity": str(quantity),
        "workingType": "MARK_PRICE",
        "timestamp": str(timestamp)
    }

    # Signatur: alphabetisch sortiert
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

    # DEINE Keys
    api_key = ""
    secret_key = ""

    symbol = data.get("symbol", "PUMP-USDT")
    trigger_price = data.get("trigger_price")
    quantity = data.get("quantity")

    # Pflichtfelder prüfen
    if trigger_price is None or quantity is None:
        return jsonify({"error": True, "msg": "trigger_price und quantity müssen im Webhook mitgegeben werden"}), 400

    trigger_price = float(trigger_price)
    quantity = float(quantity)

    # Order ausführen
    order_response = place_trigger_market_order(api_key, secret_key, symbol, quantity, trigger_price)

    return jsonify({
        "status": "trigger_order_placed",
        "symbol": symbol,
        "trigger_price": trigger_price,
        "quantity": quantity,
        "order_response": order_response
    })


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
