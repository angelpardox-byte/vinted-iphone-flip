# Bot de chollos de iPhone en Vinted

Detecta anuncios de iPhone (12 al 16) en Vinted que estén claramente por
debajo de precio de mercado, y te avisa por Telegram al instante.

## Cómo funciona

1. **Búsqueda**: lanza una búsqueda por cada modelo/variante contra el
   endpoint interno de catálogo de Vinted.
2. **Extracción**: de cada título extrae el modelo (ej. "iPhone 13 Pro") y
   la capacidad (ej. "128GB").
3. **Media móvil**: mantiene en SQLite el histórico de precios por
   combinación modelo+capacidad, y calcula la media.
4. **Detección de chollo**: un anuncio se marca como chollo si:
   - Está un % configurable por debajo de la media del grupo (por defecto 20%), **o**
   - Está por debajo de un umbral manual que definas tú para ese modelo.
5. **Notificación**: te envía un mensaje por Telegram con precio, media del
   grupo, motivo y enlace directo al anuncio.
6. **Anti-duplicados**: cada anuncio se guarda por ID, así que nunca te
   avisa dos veces del mismo.

## Instalación

```bash
pip install -r requirements.txt
```

## Configuración de Telegram

Ya tienes el bot creado (@ChollosIphone_Bot). Necesitas dos cosas:

1. **El token** (te lo dio BotFather al crear el bot).
2. **Tu chat_id**: escríbele cualquier mensaje al bot desde Telegram y
   luego visita en el navegador:
   ```
   https://api.telegram.org/bot<TU_TOKEN>/getUpdates
   ```
   Ahí verás un campo `"chat":{"id": 123456789, ...}` — ese número es tu
   `chat_id`.

Luego exporta ambos como variables de entorno:

```bash
export TELEGRAM_BOT_TOKEN="123456:ABC-DEF..."
export TELEGRAM_CHAT_ID="123456789"
```

(En Windows con PowerShell: `$env:TELEGRAM_BOT_TOKEN="..."`)

## Ejecución

```bash
# Corre en bucle continuo (recomendado, revisa cada 90s por defecto)
python main.py

# Una sola pasada (útil para probar o para lanzar por cron)
python main.py --once
```

Déjalo corriendo en un servidor barato (una VPS de 3-5€/mes, un Raspberry
Pi, o incluso tu propio PC si lo dejas encendido) para que monitorice 24/7.

## Ajustar a tu gusto (`config.py`)

- `MODELS` / `STORAGE_VARIANTS`: qué modelos y capacidades sigue.
- `PCT_BELOW_AVG`: el % de descuento sobre la media que consideras chollo.
- `MANUAL_THRESHOLDS`: precios fijos por modelo si quieres ser más
  agresivo con alguno en concreto (ej. `"iPhone 13 Pro|128GB": 350`).
- `MIN_SAMPLES_FOR_AVG`: cuántos anuncios necesita ver de un grupo antes
  de fiarse de la media (para evitar falsos positivos al principio).
- `SEARCH_INTERVAL_SECONDS`: frecuencia de refresco.
- `EXCLUDE_KEYWORDS`: palabras que descartan anuncios (piezas, roto...).

## Primeros días: "calentar" la base de datos

Al principio no habrá suficiente histórico para calcular medias fiables
(`MIN_SAMPLES_FOR_AVG`), así que los primeros días el bot solo irá
acumulando datos de precios sin avisar de nada (salvo que definas
`MANUAL_THRESHOLDS`). Es normal — a partir del 5º-10º anuncio visto por
grupo, las medias empiezan a ser útiles.

## Importante: sobre el scraping de Vinted

Vinted no tiene una API pública oficial; este bot usa el mismo endpoint
interno que su web usa para las búsquedas. Esto significa:

- Puede dejar de funcionar si Vinted cambia su endpoint — en ese caso,
  hay que inspeccionar la pestaña "Red/Network" del navegador buscando
  algo en vinted.es y ver qué URL llama.
- No hagas demasiadas peticiones seguidas (ya hay una pausa configurada
  en `REQUEST_DELAY_SECONDS`) para no arriesgarte a que te bloqueen la IP.
- Usa esto de forma personal/razonable, no como servicio a terceros.

## Próximas mejoras posibles

- Filtrar por ubicación/vendedor con buena reputación.
- Añadir un segundo canal para Wallapop (ya lo tienes en el otro proyecto).
- Guardar capturas del anuncio antes de que lo eliminen.
- Panel web sencillo para ver histórico de chollos detectados.
