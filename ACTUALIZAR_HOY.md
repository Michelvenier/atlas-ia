# ATLAS IA V4 — Publicación sobre el mismo GitHub y Supabase

No se reinicia la cartera. No se cambian las contraseñas. No se conecta ningún broker.

## Paso 1: Supabase (obligatorio antes de GitHub)

1. Abrí Supabase → proyecto `atlas-ia` → SQL Editor → New query.
2. Abrí `sql/03_motor_fci_y_estadisticas.sql` con Bloc de notas y pegá TODO el código en SQL Editor.
3. Pulsá Run. Si hay error, NO pases al paso 2: hacé una captura del error (sin claves).
4. No vuelvas a ejecutar los archivos 01 y 02; no vuelvas a inicializar los $10 millones.

La migración crea tablas `atlas_nav_intents`, `atlas_equity_history` y función segura `atlas_apply_nav_paper_fill` para simular una suscripción/rescate de FCI con VCP de fecha posterior a la orden.

## Paso 2: GitHub

1. Abrí https://github.com/Michelvenier/atlas-ia
2. `Add file` → `Upload files`.
3. Descomprimí `ATLAS_IA_MOTOR_AUTONOMO_V4_GITHUB.zip` y subí el contenido de las carpetas `app`, `docs`, `tests` y el archivo README si lo deseás. Las rutas finales deben ser:
   - `app/engine.py` (reemplazar)
   - `app/conservative.py` (nuevo)
   - `docs/index.html` (reemplazar)
   - `tests/test_conservative.py` (nuevo)
   - `sql/03_motor_fci_y_estadisticas.sql` (agregar al repositorio)
4. Confirmá `Commit changes` en `main`.
5. **No subas claves, contraseñas ni archivos `.env`.**

## Paso 3: arrancar un ciclo autónomo y verificar

1. Abrí https://github.com/Michelvenier/atlas-ia/actions/workflows/atlas.yml
2. `Run workflow` → `main` → `Run workflow`.
3. Abrí la ejecución nueva → `run` → `Ejecutar motor ficticio`.
4. Tiene que verse un resumen con `conservative_status`, `byma_open`, `news_refreshed` y `warnings`.
5. Un verde significa que **el código funcionó**, no que se haya comprado. La primera suscripción FCI debe quedar `PENDING` hasta publicarse un VCP de una fecha posterior.
6. Entrá a https://michelvenier.github.io/atlas-ia/ y verificá la nueva pestaña **Evolución ARS / USD** y el panel **Estado del perfil conservador**.

## Qué opera y qué NO opera

- **Conservador:** compras y rescates ficticios de clases MM en ARS con fecha NAV posterior; hasta $400.000 por orden y máximo $1,2M por clase / cinco sociedades administradoras, condicionado a fuentes y filtros. No hay acceso verificado a brokers ni horarios de suscripción de cada fondo.
- **Moderado:** compra y venta ficticia de SPY.BA, MSFT.BA y AAPL.BA según reglas, calendario, límite y precio posterior (con restricciones por instrumento).
- **Agresivo:** compra y venta ficticia de YPFD.BA, GGAL.BA y PAMP.BA según reglas y precio posterior.
- **Bonos, letras, ON, cauciones y otros FCI:** disponibles para investigación, **no se autoriza su negociación automática** porque faltan reglas específicas de ejecución, liquidación y fuentes suficientes.
- **Comité:** presenta argumentos explicables por reglas; no existe todavía un grupo de agentes generativos conectado a balances y noticias para decidir órdenes.
- **No garantiza ganancias**: los precios y los NAV provienen de terceros y las operaciones son simuladas, no negociaciones confirmadas. Se preservan fondos cuando no hay datos válidos.

## Fuentes utilizadas

- https://www.byma.com.ar/mercado/calendario-bursatil
- https://compararfondos.com.ar/api.html
- https://www.cnv.gov.ar/SitioWeb/FondosComunesInversion/CuotaPartes
- https://ar.dolarapi.com/docs/argentina/operations/get-dolar-bolsa
