# ATLAS IA V5 — Gestión activa de cartera ficticia

Esta actualización modifica **el mismo GitHub y Supabase** existentes, sin reiniciar el capital ni borrar las posiciones. No conecta brokers ni cursa operaciones reales.

## Cambios concretos

- **Conservador**: si no hay FCI money-market válido, consulta la API oficial de transparencia del BCRA y puede constituir un **plazo fijo FICTICIO** de $200.000 a 30 días con una TEA reportada (la admisión del cliente no puede verificarse). Un depósito activo cuenta como inversión, no como efectivo. Se capitaliza al vencimiento, sin simular rescate anticipado.
- Los FCI pasan a aceptar rendimiento de 7 días verificable cuando falta el de 30, manteniendo requisitos de moneda, VCP y fecha. La orden sigue necesitando cuotaparte **posterior** antes de registrar ejecución estimada.
- **Moderado/agresivo**: baja el umbral de entrada piloto a 64/100, amplía el universo y opera montos iniciales más pequeños ($150.000 / $100.000). Mantiene límite de volatilidad, RSI, cupo de cartera, mercado abierto, cotización reciente y precio posterior. El aumento de frecuencia no implica compra obligatoria.
- Una orden pendiente de FCI **no bloquea acciones**, ni la orden de un perfil impide evaluar al otro.
- Admite cotizaciones de hasta 35 minutos por demoras posibles del proveedor gratuito. Esto es simulación con precios informativos, **no ejecución real ni garantía de precio negociable**.
- Registra rechazos de inversión por instrumento y conserva resultados observados de decisiones a cinco y veinte días; no modifica reglas a ciegas tras una pérdida.
- Se muestran depósitos ficticios, vencimientos y estado de evaluación en el tablero; el patrimonio incluye el valor acumulado de los depósitos, no solo dinero disponible.

## Limitaciones importantes

Las operaciones no están confirmadas en una bolsa ni por bancos. Un plazo fijo nominal puede perder poder adquisitivo o valor en USD. La tasa BCRA es informativa, depende de elegibilidad/monto/canal. Un `workflow` verde **no prueba** la constitución de una inversión; verificá los eventos `TERM_OPEN`, `FCI_PENDING_NAV`, `ORDER_PENDING` y los asientos de cartera.

El comité fundamental y político con agentes de IA conversacionales todavía **no** está implementado. Bonos, ON, letras y cauciones permanecen como investigación hasta contar con ejecución simulada específica y confiable. El aprendizaje que se implementa es una evaluación de señales, no un algoritmo que garantice mejorar rendimientos.

## Fuente principal

https://api.bcra.gob.ar/transparencia/v1.0/PlazosFijos

Leer `ACTUALIZAR_HOY.md`.
