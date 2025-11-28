import requests
import time
import hmac
import hashlib

# --- Konfiguration ---
API_KEY = "HCMkr3dg22Hepo9iJWEABqptvDmEmsJBOB0Gr5MptJMuk0a8dl4p7zFCOkdpVGb2AcwDwXaCLA2Go4X0h2g"
API_SECRET = "xhnk9SG2t8dDxjae7UbUaicE8iQrbrUTUaJ6GZXnxMzsbaT3aabL90EeuqMCBLs5UBiKaTgQRyItWOKjesF0A"
BASE_URL = "https://open-api.bingx.com"  # Offizielle API

def place_trigger_market_order(symbol: str, side: str, trigger_price: float, quantity: float, position_side="LONG"):
    """
    Erstellt direkt eine Trigger-Market-Order auf BingX, um eine neue Position zu eröffnen.
    
    symbol: Markt z.B. "BTC-USDT"
    side: "BUY" oder "SELL"
    trigger_price: Preis, bei dem die Market-Order ausgelöst wird
    quantity: Menge der Position
    position_side: "LONG" oder "SHORT"
    """
    
    endpoint = "/openApi/swap/v2/trade/order"  # BingX Endpoint für Orders
    url = BASE_URL + endpoint
    
    # Payload für Trigger Order
    payload = {
        "symbol": symbol,
        "side": side.upper(),
        "type": "TRIGGER_MARKET",       # Trigger-Market Order
        "triggerPrice": round(trigger_price, 6),
        "quantity": round(quantity, 6),
        "positionSide": position_side.upper(),
        "reduceOnly": False,            # Wichtig für neue Position
        "timestamp": int(time.time() * 1000)
    }
    
    # Signatur erstellen
    query_string = "&".join([f"{key}={payload[key]}" for key in sorted(payload)])
    signature = hmac.new(API_SECRET.encode(), query_string.encode(), hashlib.sha256).hexdigest()
    payload["signature"] = signature
    
    headers = {
        "X-BX-APIKEY": API_KEY,
        "Content-Type": "application/json"
    }
    
    response = requests.post(url, json=payload, headers=headers)
    
    try:
        return response.json()
    except Exception:
        return {"error": True, "raw_response": response.text}

# --- Beispielaufruf ---
if __name__ == "__main__":
    result = place_trigger_market_order(
        symbol="PUMP-USDT",
        side="BUY",
        trigger_price=0.00298,
        quantity=10,
        position_side="LONG"
    )
    print(result)
