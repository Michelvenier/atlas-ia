# ATLAS IA V4 · Simulación autónoma y cartera ficticia

Automatización sobre el mismo repositorio GitHub Actions + Supabase + Pages.

**Capital inicial:** se lee de Supabase, no se reinicia. Distribución configurable (actualmente 60% conservador, 25% moderado, 15% agresivo).

**Simulación:** compra / venta de acciones y CEDEARs previamente habilitados con posteriores observaciones de precios. Suscripción y rescate FCI clase money market ARS al NAV de una fecha posterior; estas operaciones son estimaciones a cuotaparte, **no** órdenes reales cursadas a brokers. No se operan futuros.

**Informes:** noticias archivadas con fuente y fecha, comité explicable por reglas, auditoría de órdenes, cartera y evolución en ARS / USD MEP, con fuente y fecha de FX.

**Seguridad:** SQL de migración `sql/03_motor_fci_y_estadisticas.sql` debe ejecutarse en Supabase antes de subir `app/engine.py`. Si falta, el workflow falla de manera visible en lugar de registrar una corrida verde ficticia. Claves exclusivamente en GitHub Secrets.

**Límites:** sin ejecución real ni garantía de precios ejecutables. Fuentes gratuitas pueden tener demoras, no hay garantía de puntualidad de GitHub Actions ni de que todo día bursátil esté correctamente representado en calendarios no oficiales. FCI, bonos y ON requieren acceso/condiciones por agente que no se verifican en esta fase. El comité no es todavía un LLM financiero con balances verificados. La estrategia es experimental y no asegura preservar ni incrementar el capital.

Leer `ACTUALIZAR_HOY.md` antes de subir archivos.
