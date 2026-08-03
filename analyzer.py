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
    ACCESSORY_KEYWORDS, EXTRA_DISCOUNT_FOR_UNKNOWN_STORAGE,
)

# Modelos ordenados de más largo a más corto para no confundir
# "iPhone 12 Pro Max" con "iPhone 12" al hacer matching.
_MODELS_SORTED = sorted(MODELS, key=len, reverse=True)


def extract_model(title: str):
    t = title.lower()
    compact = t.replace(" ", "")
    for model in _MODELS_SORTED:
        m = model.lower()
        if m in t or m.replace(" ", "") in compact:
            return model
    return None


# Acepta variantes mal escritas o con otra unidad: "128 GB", "128GB", "128Gb",
# "128 gigas", "128GIGAS", "1 TB", "1TERA"...
_STORAGE_RE = re.compile(r"(\d+)\s*(TB|TERA|GB|GIGAS?|GIGABYTES?)\b", re.IGNORECASE)


def extract_storage(title: str):
    match = _STORAGE_RE.search(title)
    if not match:
        return None
    number, unit = match.group(1), match.group(2).upper()
    candidate = f"{number}TB" if unit in ("TB", "TERA") else f"{number}GB"
    return candidate if candidate in STORAGE_VARIANTS else None


_ACCESSORY_RE = re.compile(
    r"\b(" + "|".join(re.escape(kw) for kw in ACCESSORY_KEYWORDS) + r")\b",
    re.IGNORECASE,
)


def is_suspicious(listing: dict) -> bool:
    title = listing["title"].lower()
    if listing["price"] < MIN_PRICE_SANITY:
        return True
    if any(kw in title for kw in EXCLUDE_KEYWORDS):
        return True
    if _ACCESSORY_RE.search(title):
        return True
    return False


def evaluate_listing(conn, listing: dict, get_average_price_fn, get_average_price_by_model_fn=None):
    """
    Devuelve un dict con el veredicto:
      {"is_deal": bool, "reason": str, "model": str, "storage": str,
       "avg_price": float, "sample_size": int}
    o None si el anuncio no se pudo clasificar (no es iPhone reconocible).

    Si el título no deja claro la capacidad (mal escrita, abreviada, o
    simplemente no la menciona), no se descarta el anuncio: se compara
    contra la media general del modelo (todas las capacidades) usando
    get_average_price_by_model_fn, si se proporciona.
    """
    if is_suspicious(listing):
        return None

    model = extract_model(listing["title"])
    if not model:
        return None

    storage = extract_storage(listing["title"])
    storage_known = storage is not None
    if not storage_known:
        storage = "Sin especificar"

    if storage_known:
        avg_price, sample_size = get_average_price_fn(conn, model, storage)
    elif get_average_price_by_model_fn:
        avg_price, sample_size = get_average_price_by_model_fn(conn, model)
    else:
        avg_price, sample_size = 0.0, 0

    price = listing["price"]

    reasons = []
    is_deal = False

    required_discount = PCT_BELOW_AVG if storage_known else PCT_BELOW_AVG + EXTRA_DISCOUNT_FOR_UNKNOWN_STORAGE

    if sample_size >= MIN_SAMPLES_FOR_AVG and avg_price > 0:
        discount = 1 - (price / avg_price)
        if discount >= required_discount:
            is_deal = True
            reason = f"{discount:.0%} por debajo de la media ({avg_price:.0f}€)"
            if not storage_known:
                reason += " — capacidad no confirmada en el título"
            reasons.append(reason)

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
