from flask import Flask, request, jsonify
import time
import hmac
import hashlib
import requests

app = Flask(__name__)

BASE_URL = "https://open-api.bingx.com"
ORDER_ENDPOINT = "/openApi/swap/v2/trade/order"

API_KEY = "HCMkr3dg22Hepo9iJWEABqptvDmEmsJBOB0Gr5MptJMuk0a8dl4p7zFCOkdpVGb2AcwDwXaCLA2Go4X0h2g"
SECRET_KEY = "xhnk9SG2t8dDxjae7UbUaicE8iQrbrUTUaJ6GZXnxMzsbaT3aabL90EeuqMCBLs5UBiKaTgQRyItWOKjesF0A"

def generate_signature(secret_key: str, params: str) -> str:
    return hmac.new(secret_key.encode('utf-8'), params.encode('utf-8'), hashlib.sha256).hexdigest()

def place_trigger_market_order(symbol: str, usdt_amount: float, trigger_price: float, position_side="LONG"):
    
    #Trigger-Market-Order (STOP_MARKET) direkt setzen

    quantity = round(usdt_amount / trigger_price, 6)
    timestamp = int(time.time() * 1000)

    params_dict = {
        "symbol": symbol,
        "side": "BUY",               # LONG = BUY
        "type": "STOP_MARKET",       # Trigger-Market Order
        "stopPrice": round(trigger_price, 6),  # Preis, bei dem die Order ausgelöst wird
        "quantity": quantity,
        "positionSide": position_side,
        "timestamp": timestamp,
        "timeInForce": "GTC"
    }

    query_string = "&".join(f"{k}={params_dict[k]}" for k in sorted(params_dict))
    params_dict["signature"] = generate_signature(SECRET_KEY, query_string)

    url = f"{BASE_URL}{ORDER_ENDPOINT}"
    headers = {"X-BX-APIKEY": API_KEY, "Content-Type": "application/json"}
    response = requests.post(url, headers=headers, json=params_dict)
    return response.json()

@app.route('/webhook', methods=['POST'])
def webhook():
    # Nur eine Trigger-Market-Order erstellen, kein Check, kein Telegram, kein Firebase
    symbol = "BABY-USDT"
    usdt_amount = 10
    trigger_price = 0.002980
    result = place_trigger_market_order(symbol, usdt_amount, trigger_price, "LONG")
    return jsonify({"status": "trigger_order_created", "result": result})

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
