"""
Configuración central del bot de detección de chollos de iPhone en Vinted.
Ajusta aquí modelos, umbrales y credenciales.
"""
import os

# ── Telegram ──────────────────────────────────────────────────────────────
# Usa variables de entorno para no dejar el token en el código.
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")  # tu token de ChollosIphone_Bot
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")      # tu chat_id (usa /getUpdates para obtenerlo)

# ── Modelos a monitorizar ─────────────────────────────────────────────────
# Vinted permite buscar por texto libre; generamos variantes de búsqueda
# para cada modelo y capacidad.
MODELS = [
    "iPhone 12", "iPhone 12 mini", "iPhone 12 Pro", "iPhone 12 Pro Max",
    "iPhone 13", "iPhone 13 mini", "iPhone 13 Pro", "iPhone 13 Pro Max",
    "iPhone 14", "iPhone 14 Plus", "iPhone 14 Pro", "iPhone 14 Pro Max",
    "iPhone 15", "iPhone 15 Plus", "iPhone 15 Pro", "iPhone 15 Pro Max",
    "iPhone 16", "iPhone 16 Plus", "iPhone 16 Pro", "iPhone 16 Pro Max",
]

STORAGE_VARIANTS = ["64GB", "128GB", "256GB", "512GB", "1TB"]

# ── Detección de gangas ───────────────────────────────────────────────────
# Un anuncio se considera "chollo" si cumple CUALQUIERA de estas condiciones:
#   1. Precio >= PCT_BELOW_AVG por debajo de la media móvil del grupo
#      (mismo modelo + capacidad + rango de estado)
#   2. Precio por debajo del umbral manual definido en MANUAL_THRESHOLDS
PCT_BELOW_AVG = 0.20  # 20% por debajo de la media = chollo

# A partir de este descuento, el mensaje de Telegram destaca el anuncio
# como "SUPER CHOLLO" para que resalte frente al resto de avisos.
SUPER_DEAL_DISCOUNT = 0.35  # 35% por debajo de la media = super chollo

# Umbrales manuales opcionales por modelo (clave = "iPhone 13 Pro|128GB")
# Si no defines uno para una combinación, solo se usa el criterio de media móvil.
MANUAL_THRESHOLDS = {
    # "iPhone 13 Pro|128GB": 350,
    # "iPhone 14|256GB": 380,
}

# Mínimo de anuncios históricos en el grupo antes de confiar en la media
MIN_SAMPLES_FOR_AVG = 5

# ── Filtro de vendedor ────────────────────────────────────────────────────
# Antes de notificar un chollo, comprobamos el perfil del vendedor para
# evitar cuentas nuevas o sospechosas sin historial de ventas.
MIN_SELLER_ITEMS_SOLD = 1      # ha de haber vendido al menos 1 artículo antes
MIN_SELLER_REPUTATION = 0.8    # % de valoraciones positivas (0-1), solo si tiene reseñas

# Ignora anuncios claramente rotos/despiece que distorsionan la media
MIN_PRICE_SANITY = 60      # € — por debajo de esto se asume pantalla rota / piezas

# Si el título menciona explícitamente la salud de la batería y es menor a
# este porcentaje, se descarta el anuncio. Si no la menciona, no se penaliza.
MIN_BATTERY_HEALTH = 78
EXCLUDE_KEYWORDS = [
    "piezas", "roto", "no enciende", "para repuestos", "estropeado",
    "dañad", "bloqueado", "mal estado",
]

# Accesorios que mencionan el modelo en el título pero no son el móvil en sí
# (fundas, cargadores, soportes...). Sin esto, un accesorio barato se puede
# confundir con un "chollo" del móvil real cuando no menciona capacidad.
ACCESSORY_KEYWORDS = [
    "funda", "fundas", "carcasa", "carcasas", "protector de pantalla",
    "cristal templado", "cargador", "cargadores", "cable", "adaptador",
    "soporte", "correa", "mica", "power bank", "batería externa",
    "case", "cover", "screen protector", "charger", "power bank",
    "coque", "chargeur", "verre trempé",
]

# Margen de descuento adicional exigido cuando no se pudo identificar la
# capacidad exacta (se compara contra una media menos precisa, mezclando
# todas las capacidades del modelo). Solo se usa como respaldo si la IA
# no está disponible (ver más abajo).
EXTRA_DISCOUNT_FOR_UNKNOWN_STORAGE = 0.10

# ── Revisión con IA para anuncios ambiguos ──────────────────────────────────
# Para anuncios sin capacidad detectada pero con precio ya prometedor, en
# vez de aplicar el margen extra a ciegas, se le pregunta a Claude si de
# verdad parece el móvil real (y no un accesorio/pieza/anuncio dudoso).
# Si no hay clave configurada, se usa el margen extra de arriba como respaldo.
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = "claude-haiku-4-5-20251001"
MAX_AI_CALLS_PER_RUN = 8   # tope duro de consultas a la IA por cada pasada

# ── Scraping ──────────────────────────────────────────────────────────────
SEARCH_INTERVAL_SECONDS = 90       # cada cuánto relanza las búsquedas
REQUEST_DELAY_SECONDS = 3          # pausa entre requests para no saturar/parecer bot
VINTED_DOMAIN = "https://www.vinted.es"

# ── Persistencia ──────────────────────────────────────────────────────────
DB_PATH = os.path.join(os.path.dirname(__file__), "data", "listings.db")
