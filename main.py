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

from config import (
    MODELS, SEARCH_INTERVAL_SECONDS, MIN_SELLER_ITEMS_SOLD,
    MIN_SELLER_REPUTATION, MAX_AI_CALLS_PER_RUN,
)
from vinted_client import VintedClient
from storage import get_connection, already_seen, save_listing, get_average_price, get_average_price_by_model
from analyzer import evaluate_listing
from notifier import send_telegram_message, format_deal_message
from ai_reviewer import judge_listing


def log(msg: str):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}")


def seller_is_trustworthy(client: VintedClient, listing: dict) -> bool:
    """
    Comprueba que el vendedor tenga historial de ventas y buena reputación
    antes de avisar de un chollo. Si no se puede verificar (error de red,
    perfil no disponible), se descarta el aviso por precaución.
    """
    stats = client.get_seller_stats(listing.get("seller_id"))
    if stats is None:
        return False

    if stats["items_sold"] < MIN_SELLER_ITEMS_SOLD:
        return False

    if stats["feedback_count"] > 0 and stats["reputation"] is not None:
        if stats["reputation"] < MIN_SELLER_REPUTATION:
            return False

    return True


def make_ai_judge():
    """Envuelve judge_listing con un tope duro de llamadas por pasada,
    para que un pico de anuncios ambiguos nunca dispare el gasto."""
    calls_made = {"n": 0}

    def judge(listing, model_hint):
        if calls_made["n"] >= MAX_AI_CALLS_PER_RUN:
            return None
        calls_made["n"] += 1
        return judge_listing(listing, model_hint)

    return judge


def run_once(client: VintedClient, conn):
    total_new = 0
    total_deals = 0
    ai_judge = make_ai_judge()

    for model in MODELS:
        try:
            listings = client.search(model)
        except Exception as e:
            log(f"Error buscando '{model}': {e}")
            continue

        for listing in listings:
            if not listing["id"] or already_seen(conn, listing["id"]):
                continue

            verdict = evaluate_listing(conn, listing, get_average_price, get_average_price_by_model,
                                        ai_judge, searched_model=model)

            if verdict is None:
                # No reconocible como iPhone/capacidad válida: igualmente
                # lo guardamos como visto para no reprocesarlo, pero sin
                # meterlo en las estadísticas de precio.
                save_listing(conn, listing["id"], "desconocido", "desconocido",
                             listing["price"], listing["title"], listing["url"])
                continue

            notify = False
            if verdict["is_deal"]:
                if seller_is_trustworthy(client, listing):
                    notify = True
                else:
                    log(f"Chollo descartado por vendedor sin historial fiable: "
                        f"{verdict['model']} {verdict['storage']} a {listing['price']}€ "
                        f"({listing.get('seller_login', '?')})")

            save_listing(conn, listing["id"], verdict["model"], verdict["storage"],
                         listing["price"], listing["title"], listing["url"],
                         notified=notify)
            total_new += 1

            if notify:
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
