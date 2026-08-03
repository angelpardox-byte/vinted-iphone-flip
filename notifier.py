"""
Envío de notificaciones por Telegram usando el bot ChollosIphone_Bot.
"""
import requests
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, SUPER_DEAL_DISCOUNT


def send_telegram_message(text: str):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("[AVISO] Falta configurar TELEGRAM_BOT_TOKEN o TELEGRAM_CHAT_ID (variables de entorno).")
        print(text)
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    }
    try:
        resp = requests.post(url, json=payload, timeout=10)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"[ERROR] No se pudo enviar la notificación a Telegram: {e}")


def format_deal_message(listing: dict, verdict: dict) -> str:
    discount = verdict.get("discount")
    is_super = discount is not None and discount >= SUPER_DEAL_DISCOUNT
    header = "🚨🚨 <b>SUPER CHOLLO</b> 🚨🚨" if is_super else "🔥 <b>CHOLLO DETECTADO</b>"

    return (
        f"{header}\n\n"
        f"📱 {verdict['model']} {verdict['storage']}\n"
        f"💰 Precio: <b>{listing['price']:.0f}€</b>\n"
        f"📊 Media del grupo: {verdict['avg_price']:.0f}€ "
        f"(sobre {verdict['sample_size']} anuncios)\n"
        f"✅ Motivo: {verdict['reason']}\n"
        f"🏷️ Estado: {listing.get('condition', 'N/D')}\n"
        f"📝 {listing['title']}\n"
        f"🔗 {listing['url']}"
    )
