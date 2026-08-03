"""
Consulta a Claude (API de Anthropic) para juzgar anuncios ambiguos: sin
capacidad detectada en el título, pero con un precio que ya parece
interesante. Se llama solo para ese puñado de candidatos por pasada,
nunca para todos los anuncios (ver evaluate_listing en analyzer.py y el
tope MAX_AI_CALLS_PER_RUN en main.py).
"""
import requests
from config import ANTHROPIC_API_KEY, ANTHROPIC_MODEL

_API_URL = "https://api.anthropic.com/v1/messages"

_SYSTEM_PROMPT = (
    "Evalúas anuncios de segunda mano de Vinted para un bot que busca "
    "iPhones baratos. Te doy el título de un anuncio cuyo precio ya "
    "parece bueno, pero no menciona la capacidad de almacenamiento. "
    "Responde SOLO con 'SI' si es razonablemente seguro que el anuncio "
    "es un iPhone real en venta (no una funda, cargador, pieza de "
    "repuesto, accesorio, ni un móvil roto/bloqueado/para piezas). "
    "Responde SOLO con 'NO' en cualquier otro caso, incluida la duda."
)


def judge_ambiguous_listing(listing: dict):
    """
    Devuelve True si la IA cree que es un iPhone real en venta, False si
    cree que no lo es, o None si no se pudo consultar (sin clave, error
    de red, límite de crédito agotado...). Ante None, quien llame debe
    aplicar su propio criterio de respaldo.
    """
    if not ANTHROPIC_API_KEY:
        return None

    prompt = f'Título del anuncio: "{listing["title"]}"\nPrecio: {listing["price"]}€'

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
                "max_tokens": 5,
                "system": _SYSTEM_PROMPT,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=15,
        )
        resp.raise_for_status()
        text = resp.json()["content"][0]["text"].strip().upper()
        return text.startswith("SI")
    except (requests.RequestException, KeyError, IndexError, ValueError):
        return None
