# ATLAS IA — actualización integral unificada (única entrega)

Este paquete **reúne las mejoras V4, V5 y V6** (FCI, plazos fijos ficticios, evolución ARS/USD, noticias, comité por reglas, búsqueda documental y análisis técnico por tandas). Es una actualización **del mismo proyecto**, no otro sistema. No contiene claves ni reinicia los $10.000.000.

## Instalar, en este orden

1. **Supabase:** Proyecto `atlas-ia` → SQL Editor → New query. Abrir **`sql/INSTALAR_UNA_VEZ.sql`**, pegar su contenido y ejecutar `Run`. Incluye las migraciones 03 y 04 en orden. Ya deben existir las migraciones 01 y 02 originales. Si ya se ejecutaron 03 y 04 antes, no reiniciar nada: el SQL es mayormente idempotente, pero conviene una copia de seguridad antes de repetir una migración.
2. **GitHub:** Abrir `https://github.com/Michelvenier/atlas-ia` → `Add file` → `Upload files` y arrastrar **el contenido** del directorio de este paquete, conservando rutas `app/`, `docs/`, `tests/`, `requirements.txt`. Hacer `Commit changes`. GitHub Web puede impedir reemplazos de archivos existentes según cómo se arrastren: confirmar explícitamente el diff y las rutas. **No subir los archivos SQL como secretos**: son estructura, nunca contienen contraseñas.
3. **Archivo oculto de automatización:** comprobar en el repositorio **`.github/workflows/atlas.yml`**. Si GitHub no subió ese archivo por ser carpeta oculta, abrirlo directamente en GitHub y reemplazar su contenido con el del paquete. **No dejar un `workflows/` en raíz**. Este workflow ya incluye pruebas antes de ejecutar el motor.
4. **Credenciales:** mantener los dos GitHub Actions Secrets existentes `SUPABASE_URL` y `SUPABASE_SECRET_KEY`. No escribirlos en el código, en el chat o en GitHub Pages.
5. **Ejecutar:** `https://github.com/Michelvenier/atlas-ia/actions/workflows/atlas.yml` → `Run workflow` → `main`. Revisar salida de pruebas y `Ejecutar motor ficticio`. GitHub Pages se publica desde `docs/` como parte del mismo flujo.
6. **Verificar:** `https://michelvenier.github.io/atlas-ia/` y `docs/snapshot.json`. Debe aparecer `app_version: ATLAS-INTEGRAL-2026.11-consolidado`. Revisar `technical_batch_candidates`, `technical_batch_success`, `conservative_status`, `term_deposit_status`, `warnings` y el `operational_state`.

## Qué hace realmente

- Ejecuta análisis de mercado y noticias con calendario de sesiones habilitadas, respetando las restricciones implementadas. Los feriados extraordinarios no están garantizados por una API oficial.
- Analiza **documentalmente** el catálogo externo de bonos, letras, ON y FCI; cuenta y señala datos ausentes. NO son compras ni 1.000 análisis fundamentales.
- Recorre históricamente un conjunto más amplio de acciones y CEDEAR por **tandas** cada 15 minutos. Los datos Yahoo pueden ser demorados y no certifican precio ejecutable.
- Puede crear órdenes bursátiles ficticias con validación temporal y simular ejecución contra precio **posterior**; no usa brokers reales.
- Conservador: puede crear intención de suscripción/rescate FCI con siguiente cuotaparte; como alternativa puede simular plazo fijo a tasa publicada del BCRA. Si la API falla, **NO inventa tasas**, registra el error.
- Evolución patrimonial en ARS y USD MEP informativo, con advertencias si faltan precios.
- Noticias RSS guardadas en Supabase por país y sector. Comité de decisiones **por reglas**, NO son agentes LLM fundamentales/políticos completos. Sala del comité es una consulta explicativa guiada.

## Límites y criterios de aceptación

La salida verde en GitHub indica que el proceso terminó, no que hubo compraventa. **Solo hay inversión ficticia** cuando existen órdenes `FILLED`, posiciones positivas o un plazo fijo `ACTIVE`, con movimiento de efectivo consistente en Supabase. Si las fuentes de tasas, NAV o cotizaciones fallan, debe abstenerse y registrar el motivo. No prometemos 1.000 históricos completos ni garantías de rendimiento; la cobertura y las operaciones deben verificarse con datos reales.

Si la V6 ya estaba instalada, esta actualización cambia escaneo, informe y pruebas; el resto se mantiene. Es posible que una jornada completa no genere compras si los datos no autorizan ejecuciones estimadas. Se requiere validar el ciclo completo antes de declarar autonomía financiera total.
