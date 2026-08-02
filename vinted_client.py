"""
Cliente ligero para la API de búsqueda de Vinted.

Vinted no ofrece una API pública oficial, pero su propio frontend consume
un endpoint interno (/api/v2/catalog/items) que también podemos consultar
nosotros. Este cliente:
  1. Abre una sesión y obtiene las cookies/CSRF necesarias visitando la home.
  2. Lanza búsquedas por texto contra el endpoint de catálogo.

Nota: al ser un endpoint no documentado, Vinted puede cambiarlo sin aviso.
Si un día deja de funcionar, lo primero es revisar si la URL o los
parámetros han cambiado (basta con inspeccionar la pestaña Network del
navegador buscando algo manualmente en vinted.es).
"""
import time
import random
import requests

from config import VINTED_DOMAIN, REQUEST_DELAY_SECONDS

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.4 Safari/605.1.15",
]


class VintedClient:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "application/json, text/plain, */*",
        })
        self._warm_up()

    def _warm_up(self):
        """Visita la home para conseguir cookies válidas antes de pegar al API."""
        self.session.get(VINTED_DOMAIN, timeout=15)
        time.sleep(1)

    def search(self, query: str, page: int = 1, per_page: int = 40):
        """
        Busca anuncios por texto libre.
        Devuelve una lista de dicts ya normalizados con los campos que usamos.
        """
        url = f"{VINTED_DOMAIN}/api/v2/catalog/items"
        params = {
            "search_text": query,
            "page": page,
            "per_page": per_page,
            "order": "newest_first",
        }
        resp = self.session.get(url, params=params, timeout=15)

        if resp.status_code == 401 or resp.status_code == 403:
            # cookies/CSRF caducados: renovamos y reintentamos una vez
            self._warm_up()
            resp = self.session.get(url, params=params, timeout=15)

        resp.raise_for_status()
        data = resp.json()

        items = []
        for raw in data.get("items", []):
            items.append(self._normalize(raw))

        time.sleep(REQUEST_DELAY_SECONDS)
        return items

    @staticmethod
    def _normalize(raw: dict) -> dict:
        price_obj = raw.get("price", {}) or raw.get("total_item_price", {})
        user = raw.get("user") or {}
        return {
            "id": raw.get("id"),
            "title": raw.get("title", ""),
            "price": float(price_obj.get("amount", 0)) if price_obj else 0.0,
            "currency": price_obj.get("currency_code", "EUR") if price_obj else "EUR",
            "url": raw.get("url", ""),
            "photo_url": (raw.get("photo") or {}).get("url", ""),
            "brand": (raw.get("brand_title") or ""),
            "condition": raw.get("status", ""),  # "Nuevo", "Muy bueno", etc.
            "seller_id": user.get("id"),
            "seller_login": user.get("login", ""),
        }

    def get_seller_stats(self, seller_id):
        """
        Consulta el perfil del vendedor para saber si tiene historial de
        ventas y su reputación. Devuelve None si no se puede verificar
        (anuncio eliminado, error de red, bloqueo temporal, etc.).
        """
        if not seller_id:
            return None

        url = f"{VINTED_DOMAIN}/api/v2/users/{seller_id}"
        try:
            resp = self.session.get(url, timeout=15)
            if resp.status_code in (401, 403):
                self._warm_up()
                resp = self.session.get(url, timeout=15)
            resp.raise_for_status()
            user = resp.json().get("user", {})
        except (requests.RequestException, ValueError):
            return None

        return {
            "items_sold": user.get("given_item_count", 0) or 0,
            "feedback_count": user.get("feedback_count", 0) or 0,
            "reputation": user.get("feedback_reputation"),
        }
