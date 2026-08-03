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
    ACCESSORY_KEYWORDS, EXTRA_DISCOUNT_FOR_UNKNOWN_STORAGE, MIN_BATTERY_HEALTH,
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


_BATTERY_RE = re.compile(
    r"(?:bater[ií]a|battery|salud)[^%\d]{0,15}(\d{1,3})\s*%"
    r"|(\d{1,3})\s*%[^%\d]{0,15}(?:bater[ií]a|battery|salud)",
    re.IGNORECASE,
)


def extract_battery_health(title: str):
    """Busca un porcentaje de batería cerca de la palabra "batería"/"battery"/
    "salud" (en cualquier orden: "batería al 85%" o "85% de batería").
    Devuelve None si el título no menciona la batería en absoluto."""
    match = _BATTERY_RE.search(title)
    if not match:
        return None
    value = match.group(1) or match.group(2)
    pct = int(value)
    return pct if 0 <= pct <= 100 else None


def is_suspicious(listing: dict) -> bool:
    """Precio irrisorio, palabras de mal estado, o batería confirmada por
    debajo del mínimo: se descarta siempre, aunque el título deje clara la
    capacidad (un iPhone roto sigue siendo un iPhone roto aunque diga
    "128GB"). Si NO menciona la batería, no se penaliza — solo se exige el
    mínimo cuando el propio anuncio la declara."""
    title = listing["title"].lower()
    if listing["price"] < MIN_PRICE_SANITY:
        return True
    if any(kw in title for kw in EXCLUDE_KEYWORDS):
        return True
    battery = extract_battery_health(listing["title"])
    if battery is not None and battery < MIN_BATTERY_HEALTH:
        return True
    return False


def looks_like_accessory_only(title: str) -> bool:
    """Solo tiene sentido comprobar esto cuando NO se ha detectado capacidad:
    si el título dice "128GB" (o similar), es casi seguro el móvil real —
    los accesorios no tienen capacidad de almacenamiento — así que un
    anuncio tipo "iPhone 13 128GB + funda de regalo" nunca debe descartarse
    por contener la palabra "funda"."""
    return bool(_ACCESSORY_RE.search(title))


def evaluate_listing(conn, listing: dict, get_average_price_fn, get_average_price_by_model_fn=None,
                      ai_judge_fn=None, searched_model=None):
    """
    Devuelve un dict con el veredicto:
      {"is_deal": bool, "reason": str, "model": str, "storage": str,
       "avg_price": float, "sample_size": int}
    o None si el anuncio no se pudo clasificar (no es iPhone reconocible).

    Dos situaciones ambiguas se resuelven con ai_judge_fn en vez de
    descartar el anuncio a ciegas:

    1. El título no menciona ningún modelo reconocible (erratas, jerga,
       orden raro de palabras). En vez de descartarlo, se le pregunta a
       la IA si de verdad es el modelo que se estaba buscando en Vinted
       (searched_model) y, si puede, qué capacidad tiene.
    2. El modelo sí se reconoce pero la capacidad no. Se compara contra
       la media general del modelo (get_average_price_by_model_fn) y, si
       el precio ya parece un chollo, se le pregunta a la IA si de
       verdad es el móvil real antes de confiar en el resultado.

    Si ai_judge_fn no está disponible o falla (None), se usa como
    respaldo el margen extra EXTRA_DISCOUNT_FOR_UNKNOWN_STORAGE (y en el
    caso 1, sin IA disponible, se sigue descartando como hasta ahora).
    """
    if is_suspicious(listing):
        return None

    model = extract_model(listing["title"])
    ai_confirmed = False

    if model is None:
        # Ni siquiera se reconoce el modelo por texto: solo con ayuda de
        # la IA (usando el modelo que se estaba buscando como contexto)
        # se puede seguir evaluando en vez de descartar sin más.
        if not searched_model or not ai_judge_fn:
            return None
        ai_result = ai_judge_fn(listing, searched_model)
        if not ai_result or not ai_result.get("is_phone"):
            return None
        model = searched_model
        storage = ai_result.get("storage")
        ai_confirmed = True
    else:
        storage = extract_storage(listing["title"])

    storage_known = storage is not None

    if not storage_known:
        if not ai_confirmed and looks_like_accessory_only(listing["title"]):
            return None
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

    if sample_size >= MIN_SAMPLES_FOR_AVG and avg_price > 0:
        discount = 1 - (price / avg_price)

        if storage_known:
            if discount >= PCT_BELOW_AVG:
                is_deal = True
                reason = f"{discount:.0%} por debajo de la media ({avg_price:.0f}€)"
                if ai_confirmed:
                    reason += " — título poco claro, verificado por IA"
                reasons.append(reason)

        elif discount >= PCT_BELOW_AVG:
            # Capacidad desconocida pero precio ya prometedor.
            if ai_confirmed:
                # La IA ya confirmó que es el móvil real (caso 1); con
                # capacidad desconocida seguimos exigiendo el margen
                # extra por prudencia en la comparación de precio.
                if discount >= PCT_BELOW_AVG + EXTRA_DISCOUNT_FOR_UNKNOWN_STORAGE:
                    is_deal = True
                    reasons.append(
                        f"{discount:.0%} por debajo de la media ({avg_price:.0f}€) "
                        "— título poco claro, verificado por IA"
                    )
            else:
                ai_verdict = ai_judge_fn(listing, model) if ai_judge_fn else None
                if ai_verdict and ai_verdict.get("is_phone"):
                    is_deal = True
                    reasons.append(
                        f"{discount:.0%} por debajo de la media ({avg_price:.0f}€) "
                        "— capacidad no confirmada, verificado por IA"
                    )
                elif ai_verdict is None and discount >= PCT_BELOW_AVG + EXTRA_DISCOUNT_FOR_UNKNOWN_STORAGE:
                    # Sin IA disponible (o falló): respaldo con margen extra.
                    is_deal = True
                    reasons.append(
                        f"{discount:.0%} por debajo de la media ({avg_price:.0f}€) "
                        "— capacidad no confirmada en el título"
                    )

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
