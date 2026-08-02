"""
Motor de análisis:
  - Extrae modelo y capacidad a partir del título del anuncio (los títulos
    de Vinted son texto libre, no hay campo estructurado fiable).
  - Decide si un anuncio es "chollo" combinando media móvil + umbral manual.
  - Filtra anuncios sospechosos (piezas, roto, precio irrisorio).
"""
import re
from config import (
    MODELS, STORAGE_VARIANTS, PCT_BELOW_AVG, MANUAL_THRESHOLDS,
    MIN_SAMPLES_FOR_AVG, MIN_PRICE_SANITY, EXCLUDE_KEYWORDS,
)

# Modelos ordenados de más largo a más corto para no confundir
# "iPhone 12 Pro Max" con "iPhone 12" al hacer matching.
_MODELS_SORTED = sorted(MODELS, key=len, reverse=True)


def extract_model(title: str):
    t = title.lower()
    for model in _MODELS_SORTED:
        if model.lower() in t:
            return model
    return None


def extract_storage(title: str):
    t = title.upper().replace(" ", "")
    for variant in STORAGE_VARIANTS:
        if variant in t:
            return variant
    return None


def is_suspicious(listing: dict) -> bool:
    title = listing["title"].lower()
    if listing["price"] < MIN_PRICE_SANITY:
        return True
    if any(kw in title for kw in EXCLUDE_KEYWORDS):
        return True
    return False


def evaluate_listing(conn, listing: dict, get_average_price_fn):
    """
    Devuelve un dict con el veredicto:
      {"is_deal": bool, "reason": str, "model": str, "storage": str,
       "avg_price": float, "sample_size": int}
    o None si el anuncio no se pudo clasificar (no es iPhone reconocible).
    """
    if is_suspicious(listing):
        return None

    model = extract_model(listing["title"])
    storage = extract_storage(listing["title"])
    if not model or not storage:
        return None

    avg_price, sample_size = get_average_price_fn(conn, model, storage)
    price = listing["price"]

    reasons = []
    is_deal = False

    if sample_size >= MIN_SAMPLES_FOR_AVG and avg_price > 0:
        discount = 1 - (price / avg_price)
        if discount >= PCT_BELOW_AVG:
            is_deal = True
            reasons.append(f"{discount:.0%} por debajo de la media ({avg_price:.0f}€)")

    manual_key = f"{model}|{storage}"
    if manual_key in MANUAL_THRESHOLDS and price <= MANUAL_THRESHOLDS[manual_key]:
        is_deal = True
        reasons.append(f"por debajo de tu umbral manual ({MANUAL_THRESHOLDS[manual_key]}€)")

    return {
        "is_deal": is_deal,
        "reason": " y ".join(reasons) if reasons else "dentro de precio normal",
        "model": model,
        "storage": storage,
        "avg_price": avg_price,
        "sample_size": sample_size,
    }
