# ATLAS IA — Actualización sobre el mismo repositorio (11/11/2026)

## Qué sí hace este paquete
- No reinicia la base de datos Supabase, el saldo ni el histórico. No ejecuta SQL de reinicio.
- Mantiene el motor ficticio: un ciclo puede crear una orden si encuentra oportunidad, la cotización es reciente y se cumplen las reglas. Las órdenes requieren una observación de precio posterior para estimar una ejecución, y pueden quedar pendientes o no ejecutarse.
- Analiza las seis especies actualmente habilitadas por reglas técnicas, consulta otras especies para seguimiento e investiga catálogo de bonos, letras, ON y FCI sujeto a cobertura y disponibilidad del proveedor.
- Reúne noticias temáticas y guarda fuentes y fechas. Actualiza la instantánea pública al finalizar cada GitHub Action.
- Incluye una Sala del Comité **guiada por reglas** en el navegador. No es un modelo de IA generativa ni puede recibir cambios de estrategia mediante chat.
- Agrega revisiones programadas a las 12:30 y 17:30 hora argentina, además de las revisiones anteriores.
- 11/11/2026: BYMA reabre con condiciones especiales. ATLAS bloquea CEDEARs porque no tiene un simulador que asegure la liquidación T+1, y deja examinar las acciones locales con datos intradiarios válidos. No se realizan operaciones si faltan precios válidos.

## Cómo publicar una única vez
1. Entrar en https://github.com/Michelvenier/atlas-ia
2. Add file > Upload files y **arrastrar el contenido descomprimido**, no el ZIP. Conservar las carpetas `app/`, `docs/`, `.github/workflows/` en la raíz. Aceptar reemplazar los archivos existentes.
3. No incluir claves, `.env` ni archivos `.pyc`. No eliminar los archivos que ya están en GitHub.
4. Commit changes. Verificar que el repositorio tenga `.github/workflows/atlas.yml`, `app/engine.py`, `app/research.py` y `docs/index.html`.
5. GitHub > Actions > ATLAS IA - simulacion bursatil > Run workflow (main). Revisar el paso 'Ejecutar motor ficticio'.
6. Ver la publicación en https://michelvenier.github.io/atlas-ia/ una vez que GitHub Pages termine de desplegar.

## Límites y seguridad
- Se necesita que `SUPABASE_URL` y `SUPABASE_SECRET_KEY` sigan en GitHub Secrets; no copiar las credenciales en el ZIP ni en el frontend.
- El acceso a Pages puede ser público. El snapshot no publica claves, pero sí la cartera ficticia.
- Las fuentes gratuitas pueden estar demoradas o ser inexactas. Nunca representa un fill estimado como ejecución confirmada en un broker.
- No hay un calendario oficial continuamente validado contra cambios extraordinarios nuevos; para fechas posteriores a excepciones conocidas usa `exchange_calendars` y exige precios intradiarios válidos. Una verificación oficial por instrumento sigue siendo una limitación para automatización completamente confiable.
- Los 60% conservadores permanecen en efectivo hasta poder simular instrumentos conservadores apropiadamente.
- Las compras automáticas solo cubren las seis especies configuradas, y hoy CEDEARs se bloquean por condición T+1. La investigación del catálogo amplio no autoriza operaciones nuevas.
- Esta versión **no incorpora agentes generativos de IA fundamental/político**: el comité indica donde faltan evidencias.
