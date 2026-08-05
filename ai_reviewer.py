"""
Consulta a Claude (API de Anthropic) para juzgar anuncios ambiguos que las
reglas simples no pueden clasificar con confianza: título con erratas o
jerga que no coincide con ningún modelo conocido, o capacidad no indicada.
Se llama solo para ese puñado de candidatos por pasada (precio ya
prometedor, no descartado por precio/estado/batería), nunca para todos los
anuncios — ver evaluate_listing en analyzer.py y el tope
MAX_AI_CALLS_PER_RUN en main.py.
"""
import base64
import requests
from config import ANTHROPIC_API_KEY, ANTHROPIC_MODEL, STORAGE_VARIANTS

_API_URL = "https://api.anthropic.com/v1/messages"

_DEAL_REVIEW_SYSTEM_PROMPT = (
    "Eres un comprador experto de segunda mano revisando un anuncio de "
    "iPhone en Vinted que un sistema de reglas ya marcó como posible "
    "chollo por precio. Tu trabajo es la última comprobación antes de "
    "avisar al usuario: mirando el título, el precio, la media de "
    "mercado y sobre todo la FOTO real del anuncio, decide si es un "
    "chollo genuino y fiable.\n\n"
    "Rechaza si la foto muestra daños claros no mencionados en el "
    "título (pantalla rota, golpes fuertes), si no parece coincidir con "
    "el modelo descrito, si es una foto de stock/catálogo en vez de una "
    "foto real del artículo, si parece un anuncio duplicado/genérico "
    "sospechoso, o si por cualquier motivo no confiarías en él como "
    "comprador. Si la foto es razonable y coherente con el título y el "
    "precio, confirma.\n\n"
    "Responde EXCLUSIVAMENTE con una de estas dos formas, sin nada más:\n"
    "CONFIRMA|<motivo breve>\n"
    "RECHAZA|<motivo breve>"
)

_SYSTEM_PROMPT = (
    "Evalúas anuncios de segunda mano de Vinted para un bot que busca "
    "iPhones baratos. Te digo qué modelo se estaba buscando en Vinted "
    "cuando apareció este anuncio, y el título real del anuncio, que no "
    "se pudo interpretar con reglas simples (puede tener erratas, jerga, "
    "u omitir la capacidad). Decide si el anuncio es de verdad ese "
    "iPhone en venta — no una funda, cargador, pieza de repuesto, "
    "accesorio, ni un móvil roto/bloqueado/para piezas, ni un producto "
    "completamente distinto que Vinted devolvió por error. "
    "Responde EXCLUSIVAMENTE con una de estas dos formas, sin nada más "
    "de texto:\n"
    "SI|<capacidad si se identifica claramente, ej. 128GB, o DESCONOCIDA>\n"
    "NO"
)


def judge_listing(listing: dict, model_hint: str):
    """
    Pregunta a la IA si el anuncio es de verdad el iPhone indicado en
    model_hint (el modelo que se estaba buscando en Vinted), y si es
    posible, qué capacidad parece tener.

    Devuelve {"is_phone": bool, "storage": str|None} o None si no se pudo
    consultar (sin clave, error de red, crédito agotado...). Ante None,
    quien llame debe aplicar su propio criterio de respaldo.
    """
    if not ANTHROPIC_API_KEY:
        return None

    prompt = (
        f'Modelo buscado en Vinted: "{model_hint}"\n'
        f'Título real del anuncio: "{listing["title"]}"\n'
        f'Precio: {listing["price"]}€'
    )

    try:
        resp = requests.post(
            _API_URL,
            headers={
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": ANTHROPIC_MODEL,
                "max_tokens": 12,
                "system": _SYSTEM_PROMPT,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=15,
        )
        resp.raise_for_status()
        text = resp.json()["content"][0]["text"].strip().upper()
    except (requests.RequestException, KeyError, IndexError, ValueError):
        return None

    if not text.startswith("SI"):
        return {"is_phone": False, "storage": None}

    parts = text.split("|")
    storage_guess = parts[1].strip() if len(parts) > 1 else ""
    storage = storage_guess if storage_guess in STORAGE_VARIANTS else None
    return {"is_phone": True, "storage": storage}


def _fetch_image_b64(photo_url: str):
    """Descarga la foto del anuncio y la codifica en base64 para pasarla
    a Claude como imagen. Devuelve (media_type, data_b64) o None si no se
    pudo descargar (URL vacía, error de red, formato no soportado)."""
    if not photo_url:
        return None
    try:
        resp = requests.get(photo_url, timeout=15)
        resp.raise_for_status()
    except requests.RequestException:
        return None

    content_type = resp.headers.get("Content-Type", "image/jpeg").split(";")[0].strip()
    if content_type not in ("image/jpeg", "image/png", "image/webp", "image/gif"):
        content_type = "image/jpeg"

    return content_type, base64.b64encode(resp.content).decode("ascii")


def judge_deal_with_photo(listing: dict, model: str, storage: str, avg_price: float, discount):
    """
    Última comprobación antes de notificar un chollo ya confirmado por las
    reglas de precio: le pide a Claude que revise también la foto real del
    anuncio (además del título y el precio) para descartar anuncios
    dañados, engañosos o con foto de stock que las reglas no detectan.

    Devuelve {"confirmed": bool, "reason": str} o None si no se pudo
    consultar (sin clave, foto no descargable, error de red...). Ante
    None, quien llame debe aplicar su propio criterio de respaldo (seguir
    notificando, como hasta ahora).
    """
    if not ANTHROPIC_API_KEY:
        return None

    image = _fetch_image_b64(listing.get("photo_url", ""))

    content = [
        {
            "type": "text",
            "text": (
                f'Título del anuncio: "{listing["title"]}"\n'
                f'Precio: {listing["price"]}€\n'
                f'Modelo/capacidad detectados: {model} {storage}\n'
                f'Media de mercado del grupo: {avg_price:.0f}€\n'
                f'Descuento sobre la media: '
                f'{f"{discount:.0%}" if discount is not None else "desconocido"}\n'
                f'Estado declarado en Vinted: {listing.get("condition", "no especificado")}'
            ),
        }
    ]
    if image:
        media_type, data_b64 = image
        content.append({
            "type": "image",
            "source": {"type": "base64", "media_type": media_type, "data": data_b64},
        })
    else:
        content[0]["text"] += "\n(No se pudo cargar la foto del anuncio — evalúa solo con el texto.)"

    try:
        resp = requests.post(
            _API_URL,
            headers={
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": ANTHROPIC_MODEL,
                "max_tokens": 60,
                "system": _DEAL_REVIEW_SYSTEM_PROMPT,
                "messages": [{"role": "user", "content": content}],
            },
            timeout=25,
        )
        resp.raise_for_status()
        text = resp.json()["content"][0]["text"].strip()
    except (requests.RequestException, KeyError, IndexError, ValueError):
        return None

    parts = text.split("|", 1)
    verdict = parts[0].strip().upper()
    reason = parts[1].strip() if len(parts) > 1 else ""
    return {"confirmed": verdict.startswith("CONFIRMA"), "reason": reason}
