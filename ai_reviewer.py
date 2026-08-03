"""
Consulta a Claude (API de Anthropic) para juzgar anuncios ambiguos que las
reglas simples no pueden clasificar con confianza: título con erratas o
jerga que no coincide con ningún modelo conocido, o capacidad no indicada.
Se llama solo para ese puñado de candidatos por pasada (precio ya
prometedor, no descartado por precio/estado/batería), nunca para todos los
anuncios — ver evaluate_listing en analyzer.py y el tope
MAX_AI_CALLS_PER_RUN en main.py.
"""
import requests
from config import ANTHROPIC_API_KEY, ANTHROPIC_MODEL, STORAGE_VARIANTS

_API_URL = "https://api.anthropic.com/v1/messages"

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
