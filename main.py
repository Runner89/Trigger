#31.12.2025
#nicht vyn


#Botname wird ignoriert.
#Market Order mit Hebel wird gesetzt
#Hebel wird in BINGX über den Code angepasst
#Falls Hebel bei LONG 1 ist, wird 0.7% des Durschnittspreises der Liqudationspreis genommen, da es bei LONG 1x kein Liquidationspreis gibt, bei SHORT 1x gibt es einen Liquidationspreis
#Preis, welcher im JSON übergeben wurde, wird in Firebase gespeichert
#der gewichtete Durchschnittspreis wird von Firebase berechnet und entsprechend die Sell-Limit Order gesetzt
#Bei Alarm wird angegeben, ab welcher SO ein Alarm via Telegramm gesendet wird
#Verfügbares Guthaben wird ermittelt
#Ordergrösse für BO = (Verfügbares Guthaben - Sicherheit) * bo_factor; SO wird dann automatisch mal Faktor gerechet
#Ordergrösse wird in Variable gespeichert, Firebase wird nur als Backup verwendet
#StopLoss sl muss angegeben werden SL Distanz zum Liquidationspreis
#StopLoss wird jedes mal neu gesetzt, es wird x Prozent vor dem Liquiationspreis gesetzt
#Falls Firebaseverbindung fehlschlägt, wird der Durchschnittspreis aus Bingx -0.2% bzw. +0.2% für die Berechnung der Sell-Limit-Order verwendet.
#Falls Status Fehler werden für den Alarm nicht die Anzahl Kaufpreise gezählt, sondern von der Variablen alarm_counter
#Wenn action=close ist, wird Position geschlossen
#Wenn action nicht gefunden wird, ist es die Baseorder
#vyn Alarm kann benutzt werden (inkl. close-Signal) und dann folgende Alarmnachricht
#Wenn Position auf BINGX schon gelöscht wurde und bei Traidingview noch nicht, wird der nächste increase-Befehl ignoriert
#Nach x Stunden seit BO oder nach x SO wird die Sell-Limit-Order auf x % gesetzt
# bot_nr = Chart
# botname = botname
# Endet der recovery Trade auch im SL, wird eine Telegramm-Nachricht gesendet


#https://......../webhook
# action wird vom vyn genommen

#{"vyn":{{strategy.order.alert_message}}, RENDER": {"api_key": {
#    "api_key": "",
#    "secret_key": "",
#    "symbol": "BABY-USDT",
#    "botname": "Baby_Bot", # muss einmalig sein
#    "bot_nr": "1", # Nr. pro Chart
#    "position_side": "LONG",
#    "sell_percentage": 2.5,
#    "price": {{close}},
#    "leverage": 1,
#    "leverage2": 1, Hebel nach SL
#    "FIREBASE_SECRET": "",
#    "alarm": 1,
#    "pyramiding": 8, grösser als 0, wird nicht berücksichtig für Berechnung, es wird für BO gerechnet: (verfügbares Guthaben  - Sicherheit) * bo_factor
#    "sicherheit": 96, Sicherheit muss nicht mal Hebel gerechnet werden, wird im Code gemacht
#    "usdt_factor": 1.4,
#    "bo_factor": 0.001, wie viel Prozent beträgt die BO im Verhältnis zum verfügbaren Guthaben unter Berücksichtung der Gewichtung aller SO
#    "bo_factor2": 0.001, wie viel Prozent beträgt die BO im Verhältnis zum verfügbaren Guthaben unter Berücksichtung der Gewichtung aller SO nach einem SL
#    "base_time2": "", darf nur beim Testen Inhalt enthalten, 2025-08-22T11:22:37.986015+00:00, simulierter Zeitpunkt der BO
#    "after_h": 48, nach x Stunden seit BO wird Sell-Limit-Order beim nächsten Kauf auf x Prozent gesetzt oder
#    "after_so": 14, nach x SO wird Sell-Limit-Order beim nächsten Kauf auf x Prozent gesetzt
#    "sell_percentage2": 0.5,
#    "sl": 10, Stop Loss bei x Prozent setzen
#    "ma": 1, bei StopLoss muss ma 1 sein. Ansonsten 0
#    "beenden": "nein" wenn ja, wird keine neue Position nach dem Schliessen der aktuellen Position geöffnet
#    }}



#}}



from flask import Flask, request, jsonify
from datetime import datetime, timezone
import time
import hmac
import hashlib
import requests
import os
import json

app = Flask(__name__)

BASE_URL = "https://open-api.bingx.com"
BALANCE_ENDPOINT = "/openApi/swap/v2/user/balance"
ORDER_ENDPOINT = "/openApi/swap/v2/trade/order"
PRICE_ENDPOINT = "/openApi/swap/v2/quote/price"
OPEN_ORDERS_ENDPOINT = "/openApi/swap/v2/trade/openOrders"
FIREBASE_URL = os.environ.get("FIREBASE_URL", "")

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

saved_usdt_amounts = {}  # globales Dict für alle Coins
status_fuer_alle = {} 
alarm_counter = {}
base_order_times = {}
aktueller_Bot = {}
ma_Wert = {} 
recovery_trade = {} 
recovery_pending = {}


def generate_signature(secret_key: str, params: str) -> str:
    return hmac.new(secret_key.encode('utf-8'), params.encode('utf-8'), hashlib.sha256).hexdigest()

def get_futures_balance(api_key: str, secret_key: str):
    timestamp = int(time.time() * 1000)
    params = f"timestamp={timestamp}"
    signature = generate_signature(secret_key, params)
    url = f"{BASE_URL}{BALANCE_ENDPOINT}?{params}&signature={signature}"
    headers = {"X-BX-APIKEY": api_key}
    response = requests.get(url, headers=headers)
    return response.json()

def firebase_speichere_base_order_time(botname, timestamp, firebase_secret):
    url = f"{FIREBASE_URL}/base_order_time/{botname}.json?auth={firebase_secret}"
    data = timestamp.isoformat()  # nur der String
    response = requests.put(url, json=data)
    return f"Base-Order-Zeit für {botname} gespeichert: {timestamp}, Status: {response.status_code}"

def get_position_history(api_key, secret_key, symbol, start_ms, end_ms, limit=200):
    endpoint = "/openApi/swap/v2/trade/positionHistory"  # in den Docs: "Query Position History"
    params = {
        "symbol": symbol,
        "startTime": int(start_ms),
        "endTime": int(end_ms),
        "limit": int(limit),
    }
    resp = send_signed_request("GET", endpoint, api_key, secret_key, params)
    if resp.get("code") != 0:
        return []
    # je nach Response: resp["data"]["list"] oder resp["data"]
    data = resp.get("data", {})
    return data.get("list", data if isinstance(data, list) else [])

def last_5_by_side(position_history_rows, position_side):
    side = position_side.upper()
    rows = [r for r in position_history_rows if str(r.get("positionSide","")).upper() == side]
    # sortiert nach Schließzeit (oder updateTime)
    rows.sort(key=lambda r: int(r.get("closeTime", r.get("updateTime", 0))), reverse=True)
    return rows[:5]


def get_current_price(symbol: str):
    url = f"{BASE_URL}{PRICE_ENDPOINT}?symbol={symbol}"
    response = requests.get(url)
    data = response.json()
    if data.get("code") == 0 and "data" in data and "price" in data["data"]:
        return float(data["data"]["price"])
    else:
        return None

def close_open_position(api_key, secret_key, symbol, position_side="LONG"):
    """
    Schließt die offene Position sofort per Market Order.
    position_side: "LONG" oder "SHORT"
    """
    logs = []

    # 1. Aktuelle Positionsgröße und Liquidationspreis abfragen
    position_size, _, liquidation_price = get_current_position(api_key, secret_key, symbol, position_side, logs=logs)
    
    if position_size == 0:
        logs.append(f"Keine offene Position für {symbol} ({position_side}) gefunden.")
        return {"code": 1, "msg": "Keine offene Position", "logs": logs}

    # 2. Market Sell/Buy zum Schließen der Position
    side = "SELL" if position_side.upper() == "LONG" else "BUY"

    timestamp = int(time.time() * 1000)
    params_dict = {
        "symbol": symbol,
        "side": side,
        "type": "MARKET",
        "quantity": round(position_size, 6),
        "positionSide": position_side.upper(),
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
    try:
        result = response.json()
    except Exception as e:
        result = {"code": -1, "msg": f"Fehler beim Parsen der API-Antwort: {e}", "raw_response": response.text}

    logs.append(f"Schließen der Position: {result}")
    return {"result": result, "logs": logs}

def place_market_order(api_key, secret_key, symbol, usdt_amount, position_side="LONG"):
    price = get_current_price(symbol)
    if price is None:
        return {"code": 99999, "msg": "Failed to get current price"}

    quantity = round(usdt_amount / price, 6)
    timestamp = int(time.time() * 1000)

    params_dict = {
        "symbol": symbol,
        "side": "BUY",
        "type": "MARKET",
        "quantity": quantity,
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

def place_stop_loss_order(api_key, secret_key, symbol, quantity, stop_price, position_side="LONG"):
    timestamp = int(time.time() * 1000)

    params_dict = {
        "symbol": symbol,
        "side": "SELL",
        "type": "STOP_MARKET",
        "stopPrice": round(stop_price, 6),
        "quantity": round(quantity, 6),
        "positionSide": position_side,
        "timestamp": timestamp,
        "timeInForce": "GTC"
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

def send_signed_request(http_method, endpoint, api_key, secret_key, params=None):
    if params is None:
        params = {}

    timestamp = int(time.time() * 1000)
    params['timestamp'] = timestamp

    query_string = "&".join(f"{k}={params[k]}" for k in sorted(params))
    signature = hmac.new(secret_key.encode(), query_string.encode(), hashlib.sha256).hexdigest()
    params['signature'] = signature

    url = f"{BASE_URL}{endpoint}"
    headers = {"X-BX-APIKEY": api_key}

    if http_method == "GET":
        response = requests.get(url, headers=headers, params=params)
    elif http_method == "POST":
        response = requests.post(url, headers=headers, json=params)
    elif http_method == "DELETE":
        response = requests.delete(url, headers=headers, params=params)
    else:
        raise ValueError("Unsupported HTTP method")

    return response.json()

def get_current_position(api_key, secret_key, symbol, position_side, logs=None):
    endpoint = "/openApi/swap/v2/user/positions"
    params = {"symbol": symbol}
    response = send_signed_request("GET", endpoint, api_key, secret_key, params)

    positions = response.get("data", [])
    raw_positions = positions if isinstance(positions, list) else []

    if logs is not None:
        logs.append(f"Positions Rohdaten: {raw_positions}")

    position_size = 0
    liquidation_price = None

    if response.get("code") == 0:
        for pos in positions:
            if pos.get("symbol") == symbol and pos.get("positionSide", "").upper() == position_side.upper():
                if logs is not None:
                    logs.append(f"Gefundene Position: {pos}")
                try:
                    position_size = float(pos.get("size", 0)) or float(pos.get("positionAmt", 0))
                    liquidation_price = float(pos.get("liquidationPrice", 0))
                    if logs is not None:
                        logs.append(f"Position size: {position_size}, Liquidation price: {liquidation_price}")
                except (ValueError, TypeError) as e:
                    position_size = 0
                    if logs is not None:
                        logs.append(f"Fehler beim Parsen: {e}")
                break
    else:
        if logs is not None:
            logs.append(f"API Antwort Fehlercode: {response.get('code')}")

    return position_size, raw_positions, liquidation_price

def place_limit_sell_order(api_key, secret_key, symbol, quantity, limit_price, position_side="LONG"):
    timestamp = int(time.time() * 1000)

    params_dict = {
        "symbol": symbol,
        "side": "SELL",
        "type": "LIMIT",
        "quantity": round(quantity, 6),
        "price": round(limit_price, 6),
        "timeInForce": "GTC",
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

def firebase_loesche_base_order_time(botname, firebase_secret):
    #    Löscht den Base-Order-Zeitpunkt eines Bots in Firebase.
    try:
        url = f"{FIREBASE_URL}/base_order_time/{botname}.json?auth={firebase_secret}"
        response = requests.delete(url)
        response.raise_for_status()
        return f"Base-Order-Zeitpunkt für {botname} gelöscht, Status: {response.status_code}"
    except Exception as e:
        return f"Fehler beim Löschen des Base-Order-Zeitpunkts für {botname}: {e}"
    

def sende_telegram_nachricht(botname, text):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return "Telegram nicht konfiguriert"
    full_text = f"[{botname}] {text}"
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": full_text}
    response = requests.post(url, json=payload)
    return f"Telegram Antwort: {response.status_code}"

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

def get_open_orders(api_key, secret_key, symbol):
    timestamp = int(time.time() * 1000)
    params = f"symbol={symbol}&timestamp={timestamp}"
    signature = generate_signature(secret_key, params)
    url = f"{BASE_URL}{OPEN_ORDERS_ENDPOINT}?{params}&signature={signature}"
    headers = {"X-BX-APIKEY": api_key}
    response = requests.get(url, headers=headers)

    try:
        data = response.json()
    except ValueError:
        return {"code": -1, "msg": "Ungültige API-Antwort", "raw_response": response.text}

    return data

def cancel_order(api_key, secret_key, symbol, order_id):
    timestamp = int(time.time() * 1000)
    params = f"symbol={symbol}&orderId={order_id}&timestamp={timestamp}"
    signature = generate_signature(secret_key, params)
    url = f"{BASE_URL}{ORDER_ENDPOINT}?{params}&signature={signature}"
    headers = {"X-BX-APIKEY": api_key}
    response = requests.delete(url, headers=headers)
    return response.json()

# --- Firebase Funktionen jetzt mit botname statt asset ---
def firebase_speichere_ordergroesse(botname, betrag, firebase_secret):
    url = f"{FIREBASE_URL}/ordergroesse/{botname}.json?auth={firebase_secret}"
    data = {"usdt_amount": betrag}
    response = requests.put(url, json=data)
    return f"Ordergröße für {botname} gespeichert: {betrag}, Status: {response.status_code}"

def firebase_set_aktueller_bot(bot_nr, botname, firebase_secret):
    url = f"{FIREBASE_URL}/aktueller_Bot/{bot_nr}.json?auth={firebase_secret}"
    data = {
        "botname": botname
    }
    response = requests.put(url, json=data)
    return f"aktueller_Bot[{bot_nr}] gesetzt: {botname}, Status: {response.status_code}"


def firebase_delete_aktueller_bot(bot_nr, firebase_secret):
    url = f"{FIREBASE_URL}/aktueller_Bot/{bot_nr}.json?auth={firebase_secret}"
    response = requests.delete(url)
    return f"aktueller_Bot[{bot_nr}] gelöscht, Status: {response.status_code}"


def firebase_bot_is_active(bot_nr, botname, firebase_secret):
    url = f"{FIREBASE_URL}/aktueller_Bot.json?auth={firebase_secret}"
    try:
        response = requests.get(url)
        if response.status_code != 200:
            return False  # Fehler beim Zugriff auf Firebase

        aktueller_bot_firebase = response.json()  # sollte dict oder None sein
        if not aktueller_bot_firebase:
            return False  # kein Eintrag vorhanden

        # Prüfen, ob bot_nr vorhanden ist
        if str(bot_nr) in aktueller_bot_firebase:
            # Prüfen, ob botname übereinstimmt
            if aktueller_bot_firebase[str(bot_nr)] == botname:
                return True
            else:
                return False
        else:
            return False

    except Exception as e:
        print(f"Fehler bei Firebase-Abfrage: {e}")
        return False



def firebase_lese_ordergroesse(botname, firebase_secret):
    url = f"{FIREBASE_URL}/ordergroesse/{botname}.json?auth={firebase_secret}"
    response = requests.get(url)
    if response.status_code != 200:
        return None
    try:
        data = response.json()
        if isinstance(data, dict) and "usdt_amount" in data:
            return float(data["usdt_amount"])
        elif isinstance(data, (int, float)):
            return float(data)
    except Exception as e:
        print(f"[Fehler] Firebase JSON Parsing: {e}")
    return None

def firebase_loesche_ordergroesse(botname, firebase_secret):
    url = f"{FIREBASE_URL}/ordergroesse/{botname}.json?auth={firebase_secret}"
    response = requests.delete(url)
    return f"Ordergröße für {botname} gelöscht, Status: {response.status_code}"

def firebase_speichere_kaufpreis(botname, price, usdt_amount, firebase_secret):
    import requests


    # Daten, die gespeichert werden sollen
    data = {
        "price": price,
        "usdt_amount": usdt_amount
    }

    # URL zusammenbauen mit Authentifizierung
    url = f"{FIREBASE_URL}/kaufpreise/{botname}.json?auth={firebase_secret}"

    # HTTP PUT oder POST, je nach Bedarf
    response = requests.post(url, json=data)

    if response.status_code == 200:
        return f"Kaufpreis für {botname} erfolgreich gespeichert."
    else:
        raise Exception(f"Fehler beim Speichern: {response.text}")

def firebase_loesche_kaufpreise(botname, firebase_secret):
    url = f"{FIREBASE_URL}/kaufpreise/{botname}.json?auth={firebase_secret}"
    response = requests.delete(url)
    if response.status_code == 200:
        return f"Kaufpreise für {botname} gelöscht."
    return f"Fehler beim Löschen der Kaufpreise für {botname}: Status {response.status_code}"

def firebase_lese_kaufpreise(botname, firebase_secret):
    try:
        url = f"{FIREBASE_URL}/kaufpreise/{botname}.json?auth={firebase_secret}"
        r = requests.get(url)
        print(f"Firebase Antwort Status: {r.status_code}")
        print(f"Firebase Antwort Inhalt: {r.text}")
        daten = r.json()
        if not daten:
            print("Keine Daten unter kaufpreise/{botname} gefunden")
            return []
        # Werte in Liste umwandeln
        return [{"price": float(v.get("price", 0)), "usdt_amount": float(v.get("usdt_amount", 0))} for v in daten.values()]
    except Exception as e:
        print(f"Fehler beim Lesen der Kaufpreise: {e}")
        return []


def firebase_setze_ma_wert(bot_nr, wert, firebase_secret):
    try:
        url = f"{FIREBASE_URL}/MA/{bot_nr}.json?auth={firebase_secret}"
        response = requests.put(url, json=wert)  # <-- sauber
        return f"MA/{bot_nr} = {wert} gesetzt. Status: {response.status_code}, Body: {response.text}"
    except Exception as e:
        return f"Exception beim Setzen von MA/{bot_nr}: {e}"

def firebase_loesche_ma_bot(bot_nr, firebase_secret):
    try:
        url = f"{FIREBASE_URL}/MA/{bot_nr}.json?auth={firebase_secret}"
        response = requests.delete(url)

        if response.status_code == 200:
            return f"MA/{bot_nr} erfolgreich gelöscht."
        else:
            return f"Fehler beim Löschen von MA/{bot_nr}: Status {response.status_code}"

    except Exception as e:
        return f"Exception beim Löschen von MA/{bot_nr}: {e}"

def firebase_lese_ma_wert(bot_nr, firebase_secret):
    try:
        url = f"{FIREBASE_URL}/MA/{bot_nr}.json?auth={firebase_secret}"
        r = requests.get(url, timeout=5)
        if r.status_code != 200:
            return 0
        val = r.json()
        return int(val) if val is not None else 0
    except Exception as e:
        print(f"Fehler beim Lesen von MA/{bot_nr}: {e}")
        return 0
        

def berechne_durchschnittspreis(käufe):
    if not käufe:
        return None

    gesamtwert = 0
    gesamtmenge = 0

    for kauf in käufe:
        preis = float(kauf.get("price", 0))
        menge = float(kauf.get("usdt_amount", 0))
        gesamtwert += preis * menge
        gesamtmenge += menge

    if gesamtmenge == 0:
        return None

    return round(gesamtwert / gesamtmenge, 6)

def firebase_lese_base_order_time(botname, firebase_secret):
    try:
        url = f"{FIREBASE_URL}/base_order_time/{botname}.json?auth={firebase_secret}"
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        if data:
            return data.get("base_order_time")  # ISO-Zeitstring
        return None
    except Exception as e:
        print(f"Fehler beim Lesen des Base-Order-Zeitpunkts aus Firebase für {botname}: {e}")
        return None
    
def set_leverage(api_key, secret_key, symbol, leverage, position_side="LONG"):
    endpoint = "/openApi/swap/v2/trade/leverage"

    params = {
        "symbol": symbol,
        "leverage": int(leverage),
        "side": position_side.upper()  # LONG oder SHORT
    }

    return send_signed_request("POST", endpoint, api_key, secret_key, params)

from datetime import datetime

def extract_closed_positions_with_pnl(position_history, position_side, limit=5):
    result = []

    rows = [
        r for r in position_history
        if r.get("positionSide", "").upper() == position_side.upper()
    ]

    rows.sort(
        key=lambda r: int(r.get("closeTime", r.get("updateTime", 0))),
        reverse=True
    )

    for r in rows[:limit]:
        entry = float(r.get("avgOpenPrice", 0))
        exitp = float(r.get("avgClosePrice", 0))
        qty = float(r.get("closedSize", r.get("size", 0)))
        pnl = float(r.get("realizedPnl", r.get("profit", 0)))

        pnl_pct = 0
        if entry > 0:
            pnl_pct = round((exitp - entry) / entry * 100, 2)

        close_ts = r.get("closeTime")
        close_time = (
            datetime.fromtimestamp(int(close_ts)/1000, tz=timezone.utc).isoformat()
            if close_ts else None
        )

        result.append({
            "symbol": r.get("symbol"),
            "side": position_side,
            "qty": qty,
            "entryPrice": entry,
            "exitPrice": exitp,
            "pnl": round(pnl, 4),
            "pnlPct": pnl_pct,
            "closeTime": close_time
        })

    return result





@app.route('/webhook', methods=['POST'])
def webhook():
    global saved_usdt_amounts
    global status_fuer_alle
    global alarm_counter
    global base_order_times
    global aktueller_Bot    
    global ma_Wert
    global recovery_trade
    global recovery_pending

    data = request.json
    logs = []

    position_side = data.get("RENDER", {}).get("position_side") or data.get("RENDER", {}).get("positionSide") or "LONG"    #data.get("position_side") or data.get("positionSide") or "LONG"

    if position_side == "LONG":  

        data = request.json or {}
        logs = []
    

    
        # Eingabewerte
        pyramiding = float(data.get("RENDER", {}).get("pyramiding", 1))  #float(data.get("pyramiding", 1))
        leverageB = float(data.get("RENDER", {}).get("leverage", 1))     #float(data.get("leverage", 1))
        sicherheit = float(data.get("RENDER", {}).get("sicherheit", 0))  #* leverageB)    #float(data.get("sicherheit", 0) * leverageB)
        sell_percentage = data.get("RENDER", {}).get("sell_percentage")    #data.get("sell_percentage")
        api_key = data.get("RENDER", {}).get("api_key")    #data.get("api_key")
        secret_key = data.get("RENDER", {}).get("secret_key")   #data.get("secret_key")
        position_side = data.get("RENDER", {}).get("position_side") or data.get("RENDER", {}).get("positionSide") or "LONG"    #data.get("position_side") or data.get("positionSide") or "LONG"
        firebase_secret = data.get("RENDER", {}).get("FIREBASE_SECRET")    #data.get("FIREBASE_SECRET")
        price_from_webhook = data.get("RENDER", {}).get("price")    #data.get("price")
        usdt_factor = float(data.get("RENDER", {}).get("usdt_factor", 1))    #float(data.get("usdt_factor", 1))
        bo_factor = float(data.get("RENDER", {}).get("bo_factor", 0.0001))    #float(data.get("bo_factor", 0.0001))
        bo_factor2 = float(data.get("RENDER", {}).get("bo_factor2", 0.0001))    #float(data.get("bo_factor", 0.0001))
        action = data.get("vyn", {}).get("action", "").lower()    #KOMMT VON VYN     data.get("action", "").lower()
        base_time2 = data.get("RENDER", {}).get("base_time2")
        after_h = data.get("RENDER", {}).get("after_h")
        after_so = data.get("RENDER", {}).get("after_so")
        sell_percentage2 = data.get("RENDER", {}).get("sell_percentage2")
        beenden = data.get("RENDER", {}).get("beenden", "nein")
        sl = data.get("RENDER", {}).get("sl")
        bot_nr = data.get("RENDER", {}).get("bot_nr")
        ma = int(data.get("RENDER", {}).get("ma", 0))
        leverage2 = int(data.get("RENDER", {}).get("leverage2", 0))

        
     
    
        now_ms = int(time.time() * 1000)
        start_ms = now_ms - 1000 * 60 * 60 * 24 * 7  # letzte 7 Tage
    
        position_history = get_position_history(
            api_key=api_key,
            secret_key=secret_key,
            symbol=symbol,
            start_ms=start_ms,
            end_ms=now_ms,
            limit=200
        )
        
        
        return jsonify({
            "error": False,
            "order_result": order_response,
            "limit_order_result": limit_order_response,
            "symbol": symbol,
            "botname": botname,
            "usdt_amount": usdt_amount,
            "sell_quantity": sell_quantity,
            "price_from_webhook": price_from_webhook,
            "sell_percentage": sell_percentage,
            "firebase_average_price": durchschnittspreis,
            "firebase_all_prices": kaufpreise,
            "usdt_balance_before_order": available_usdt,
            "stop_loss_price": stop_loss_price if liquidation_price else None,
            "stop_loss_price": stop_loss_price if 'stop_loss_price' in locals() else None,
            "saved_usdt_amount": saved_usdt_amounts,
            "status_fuer_alle": status_fuer_alle,
            "Botname": botname,
            "position_history": position_history,
            "logs": logs
        })
        
        

if __name__ == "__main__":
    # Achtung: debug=True in Produktion ausschalten
    app.run(debug=True, host="0.0.0.0", port=5000)
        
        
