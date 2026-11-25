import time
import json
import requests
from datetime import datetime, timezone, timedelta

with open("config.json") as f:
    cfg = json.load(f)

WEBHOOK_URL = cfg["webhook_url"]
UMBRAL = cfg["umbral"]
INTERVALO = cfg["intervalo"]
INTERVALO_INFORME = cfg["intervalo_informe"]

COLOMBIA = timezone(timedelta(hours=-5))


def precio_yahoo():
    url = "https://query1.finance.yahoo.com/v8/finance/chart/COP=X?interval=1m&range=1d"
    r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
    r.raise_for_status()
    return float(r.json()["chart"]["result"][0]["meta"]["regularMarketPrice"])


def precio_respaldo():
    r = requests.get("https://open.er-api.com/v6/latest/USD", timeout=10)
    r.raise_for_status()
    return float(r.json()["rates"]["COP"])


def precio_dolar():
    try:
        return precio_yahoo(), "Yahoo Finance"
    except Exception as e:
        print("Yahoo falló, usando respaldo:", e)
        return precio_respaldo(), "ExchangeRate-API (respaldo)"


def notificar(mensaje):
    try:
        r = requests.post(WEBHOOK_URL, json={"content": mensaje}, timeout=10)
        r.raise_for_status()
    except Exception as e:
        print(f"No se pudo enviar el mensaje: {e}")


def armar_informe(actual, fuente, historial, precio_anterior):
    hora = datetime.now(COLOMBIA).strftime("%I:%M %p")
    lineas = [
        f"📊 **INFORME DEL DÓLAR** · {hora}",
        f"💵 Precio actual: **${actual:,.2f} COP**",
    ]
    if precio_anterior:
        cambio = actual - precio_anterior
        pct = cambio / precio_anterior * 100
        flecha = "📈" if cambio >= 0 else "📉"
        lineas.append(f"{flecha} Cambio vs informe anterior: {cambio:+,.2f} ({pct:+.2f}%)")
    if historial:
        lineas.append(f"⬆️ Máximo del periodo: ${max(historial):,.2f}")
        lineas.append(f"⬇️ Mínimo del periodo: ${min(historial):,.2f}")
    distancia = actual - UMBRAL
    if distancia >= 0:
        lineas.append(f"🎯 Alerta en ${UMBRAL:,} · estás a ${distancia:,.2f} de distancia")
    else:
        lineas.append(f"🚨 Estás ${-distancia:,.2f} POR DEBAJO de ${UMBRAL:,}")
    lineas.append(f"Fuente: {fuente}")
    return "\n".join(lineas)


alerta_enviada = False
ultimo_informe = 0          # 0 = manda el primer informe al arrancar
precio_ultimo_informe = None
historial = []

while True:
    try:
        actual, fuente = precio_dolar()
        print(f"Dolar: {actual:.2f} COP ({fuente})")
        historial.append(actual)
        ahora = time.time()

        # ALERTA inmediata si baja del umbral (una sola vez)
        if actual < UMBRAL and not alerta_enviada:
            notificar(f"🚨🚨 **ALERTA: EL DÓLAR BAJÓ DE ${UMBRAL:,}** 🚨🚨\n"
                      f"Precio actual: **${actual:,.2f} COP**")
            alerta_enviada = True
        elif actual >= UMBRAL and alerta_enviada:
            notificar(f"✅ El dólar volvió a ${actual:,.2f} COP (sobre ${UMBRAL:,}).")
            alerta_enviada = False

        # INFORME periódico
        if ahora - ultimo_informe >= INTERVALO_INFORME:
            notificar(armar_informe(actual, fuente, historial, precio_ultimo_informe))
            ultimo_informe = ahora
            precio_ultimo_informe = actual
            historial = []

    except Exception as e:
        print("Error:", e)

    time.sleep(INTERVALO)