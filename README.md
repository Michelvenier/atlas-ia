# ATLAS IA — Nube, cartera ficticia

Repo para ejecutar automáticamente una cartera ficticia con GitHub Actions, almacenar estado y registros en Supabase y mostrar un dashboard de solo lectura mediante GitHub Pages.

## Qué hace realmente

- Presupuesto inicial de ARS 10.000.000 **ya existente en Supabase** (no vuelve a insertarlo).
- Conservador 60%: se queda en efectivo hasta incorporar mercado/renta fija adecuada.
- Moderado 25%, agresivo 15%: evalúa un universo inicial de 6 instrumentos de BYMA.
- Descarga cotizaciones históricas e intradiarias públicas de Yahoo Finance (pueden retrasarse o faltar).
- Calcula medias móviles, RSI y volatilidad y registra el motivo de las decisiones.
- **Si habilitás los dos controles de Supabase**, crea órdenes límite ficticias cuando encuentra oportunidades técnicas y el mercado figura abierto. Solo marca fills estimados con observación de precio posterior, de la misma sesión, con costes y límites.
- Es un **piloto cuantitativo**, NO un comité de IA fundamental y político ya desarrollado. Las noticias se registran, pero no gobiernan todavía la operación. No hay broker.
- El simulador no confirma liquidez de libro de órdenes; **las ejecuciones son hipotéticas y el rendimiento no es verificable como operación real**.
- Si no hay dato, sesión válida, señal o habilitación, no compra. Fines de semana: sin órdenes.

## Preparación, una sola vez

1. En tu proyecto existente `atlas-ia` de Supabase > SQL Editor, ejecutá `sql/02_motor_atlas.sql` (el esquema 01 YA está creado, no lo repitas).
2. En GitHub creá un repo nuevo llamado `atlas-ia`, **público solo si aceptás que el tablero de tu cartera ficticia pueda verlo cualquier persona con el enlace**.
3. Subí **todo el contenido** de esta carpeta a la raíz del repositorio, incluida la carpeta oculta `.github/workflows/`.
4. En GitHub > Settings > Secrets and variables > Actions > New repository secret, configurá:
   - `SUPABASE_URL`: Project URL de Supabase, ejemplo `https://xxxxxxxx.supabase.co` (no es una contraseña).
   - `SUPABASE_SECRET_KEY`: clave **service_role (legacy)** de Supabase, necesaria para este cliente REST. No uses la contraseña de la base de datos ni la publishable/anon key. **Nunca** la pegues en HTML, archivo ni chat.
5. En el repositorio GitHub > Actions > `ATLAS IA - simulacion bursatil` > Run workflow. Revisá el registro. Si falta una clave, el proceso fallará con error claro y no realizará operaciones.
6. En GitHub > Settings > Pages > Build and deployment > Deploy from a branch > Branch `main`, Folder `/docs` > Save. En unos minutos verás la URL `https://TU_USUARIO.github.io/atlas-ia/` si el repositorio es público y GitHub Pages termina de publicar. **Ese es el enlace web, no localhost.**
7. ATLAS se inicia con autonomía y trading DESACTIVADOS. Cuando hayas visto el snapshot publicado y los logs, en Supabase SQL Editor:

```sql
update public.atlas_portfolios
set autonomy_enabled=true, trading_enabled=true
where code='ATLAS-DEMO-001' and simulation_only=true;
```

Este paso únicamente habilita **operaciones ficticias** en el motor programado. No mueve dinero real.

## Horarios programados

GitHub Actions programa preapertura 08:30, revisión 10:00, cada 15 minutos aproximados en franja 10–18 h y cierre 19:15 (zona America/Argentina/Buenos_Aires). **GitHub no garantiza puntualidad**; puede demorar u omitir un ciclo. El motor valida `exchange_calendars` y marcas de tiempo y bloquea ejecuciones sin datos recientes. Feriados extraordinarios no publicados en el calendario de la biblioteca requieren un mecanismo adicional de fuentes oficiales; **no prometemos detección completa**. La compilación incluye bloqueos expresos para 2026-11-09 y 2026-11-10 pero NO son una solución general de calendario oficial.

## Dashboard público

La página de GitHub Pages lee `snapshot.json`, que Actions genera durante cada corrida y publica directamente como artefacto de Pages (no se graba en el repositorio). El dashboard no contiene claves de Supabase, ni permite realizar cambios. **La información ficticia del snapshot es pública cuando el repositorio y Pages son públicos.** Si querés privacidad, necesitaremos autenticación Supabase y RLS por usuario antes de publicar el dashboard.

## Cómo obtener las claves sin compartirlas

En Supabase > Project Settings > API Keys, buscá la clave **service_role** (legacy) y guardala exclusivamente como `SUPABASE_SECRET_KEY` en GitHub Actions Secrets. La URL está en Project Settings > Data API. Jamás publiques ni envíes la clave por chat.

## Advertencias operativas

- No recomendar para decisiones de dinero real.
- Yahoo Finance no garantiza latencia ni calidad del mercado local. En casos de retrasos, el motor no operará.
- Los fills son estimaciones, no ejecuciones verificadas; el precio bid/ask y la liquidez pueden cambiar.
- No incorpora ajuste completo por cambio de moneda; por eso solo compra activos cotizados en ARS.
- No incluye futuros, derivados ni apalancamiento.
- El workflow despliega GitHub Pages usando permisos `pages: write` e `id-token: write`, sin modificar ni subir commits al repositorio.
- Las acciones programadas ejecutan en la rama predeterminada. Un repositorio inactivo puede dejar de ejecutar agendas según políticas de GitHub.
- El dashboard no se actualiza continuamente: refleja la última ejecución completada de Actions.
- Nunca subas contraseñas de base de datos ni claves privadas al repositorio.
