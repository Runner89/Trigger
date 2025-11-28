import time
import hmac
import hashlib
import requests

BASE_URL = "https://open-api.bingx.com"
ORDER_ENDPOINT = "/openApi/swap/v2/trade/order"

API_KEY = "DEIN_API_KEY"
SECRET_KEY = "DEIN_SECRET_KEY"

def generate_signature(secret_key: str, params: str) -> str:
    return hmac.new(secret_key.encode('utf-8'), params.encode('utf-8'), hashlib.sha256).hexdigest()

def place_trigger_market_order(symbol: str, usdt_amount: float, trigger_price: float, position_side="LONG"):
    """
    Direkt Trigger-Market-Order (STOP_MARKET) setzen
    """
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
    headers = {
        "X-BX-APIKEY": API_KEY,
        "Content-Type": "application/json"
    }

    response = requests.post(url, headers=headers, json=params_dict)
    return response.json()


# Beispiel: direkt Trigger-Market-Order für 10 USDT bei Kurs 0.002980 setzen
result = place_trigger_market_order(symbol="BABY-USDT", usdt_amount=10, trigger_price=0.002980, position_side="LONG")
print(result)
