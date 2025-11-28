import requests
import time
import hmac
import hashlib
from urllib.parse import urlencode

API_KEY = "HCMkr3dg22Hepo9iJWEABqptvDmEmsJBOB0Gr5MptJMuk0a8dl4p7zFCOkdpVGb2AcwDwXaCLA2Go4X0h2g"
API_SECRET = "xhnk9SG2t8dDxjae7UbUaicE8iQrbrUTUaJ6GZXnxMzsbaT3aabL90EeuqMCBLs5UBiKaTgQRyItWOKjesF0A"
BASE_URL = "https://open-api.bingx.com"

def place_trigger_market_order(symbol, side, trigger_price, quantity, position_side="LONG"):
    endpoint = "/openApi/swap/v2/trade/order"
    url = BASE_URL + endpoint
    
    payload = {
        "symbol": symbol,
        "side": side.upper(),
        "type": "TRIGGER_MARKET",
        "triggerPrice": f"{trigger_price:.6f}",
        "quantity": f"{quantity:.6f}",
        "positionSide": position_side.upper(),
        "reduceOnly": "false",
        "timestamp": int(time.time() * 1000)
    }
    
    # URL-encode und signieren
    query_string = urlencode(sorted(payload.items()))
    signature = hmac.new(API_SECRET.encode(), query_string.encode(), hashlib.sha256).hexdigest()
    payload["signature"] = signature
    
    headers = {
        "X-BX-APIKEY": API_KEY,
        "Content-Type": "application/json"
    }
    
    response = requests.post(url, json=payload, headers=headers)
    return response.json()

if __name__ == "__main__":
    result = place_trigger_market_order(
        symbol="BABY-USDT",
        side="BUY",
        trigger_price=0.002980,
        quantity=10,
        position_side="LONG"
    )
    print(result)
