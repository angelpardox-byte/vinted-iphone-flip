"""
Bot de detección de chollos de iPhone en Vinted.

Uso:
    python main.py            # corre en bucle infinito
    python main.py --once     # una sola pasada (útil para probar o para cron)

Configura antes las variables de entorno:
    export TELEGRAM_BOT_TOKEN="tu_token"
    export TELEGRAM_CHAT_ID="tu_chat_id"

Y ajusta config.py a tu gusto (modelos, umbrales, intervalo).
"""
import sys
import time
import traceback
from datetime import datetime

from config import MODELS, SEARCH_INTERVAL_SECONDS
from vinted_client import VintedClient
from storage import get_connection, already_seen, save_listing, get_average_price
from analyzer import evaluate_listing
from notifier import send_telegram_message, format_deal_message


def log(msg: str):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}")


def run_once(client: VintedClient, conn):
    total_new = 0
    total_deals = 0

    for model in MODELS:
        try:
            listings = client.search(model)
        except Exception as e:
            log(f"Error buscando '{model}': {e}")
            continue

        for listing in listings:
            if not listing["id"] or already_seen(conn, listing["id"]):
                continue

            verdict = evaluate_listing(conn, listing, get_average_price)

            if verdict is None:
                # No reconocible como iPhone/capacidad válida: igualmente
                # lo guardamos como visto para no reprocesarlo, pero sin
                # meterlo en las estadísticas de precio.
                save_listing(conn, listing["id"], "desconocido", "desconocido",
                             listing["price"], listing["title"], listing["url"])
                continue

            save_listing(conn, listing["id"], verdict["model"], verdict["storage"],
                         listing["price"], listing["title"], listing["url"],
                         notified=verdict["is_deal"])
            total_new += 1

            if verdict["is_deal"]:
                total_deals += 1
                msg = format_deal_message(listing, verdict)
                send_telegram_message(msg)
                log(f"CHOLLO -> {verdict['model']} {verdict['storage']} a {listing['price']}€")

    log(f"Pasada completa: {total_new} anuncios nuevos, {total_deals} chollos detectados.")


def main():
    once = "--once" in sys.argv
    client = VintedClient()
    conn = get_connection()

    if once:
        run_once(client, conn)
        return

    log("Bot iniciado. Monitorizando Vinted en bucle...")
    while True:
        try:
            run_once(client, conn)
        except Exception:
            log("Error inesperado en el ciclo principal:")
            traceback.print_exc()
        time.sleep(SEARCH_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
