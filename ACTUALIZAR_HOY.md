# Cómo actualizar ATLAS V5 sin reemplazar todo el proyecto

1. **Antes de GitHub**, en Supabase > proyecto atlas-ia > SQL Editor > New query, ejecutar **todo** el contenido de `sql/04_plazos_fijos_ficticios.sql`. Solo este SQL; no repetir 01, 02 ni 03. No poner contraseñas en el chat.
2. En el repositorio `https://github.com/Michelvenier/atlas-ia` actualizar las rutas exactamente:
   - `app/engine.py` (reemplazar)
   - `app/conservative.py` (reemplazar)
   - `app/term_deposit.py` (agregar)
   - `docs/index.html` (reemplazar)
   - `sql/04_plazos_fijos_ficticios.sql` (agregar al repositorio para registro)
   - `tests/test_active.py` (opcional)
   No modificar `.github/workflows/atlas.yml`, ni los secretos, ni la base de datos original.
3. Hacer commit en rama `main`, luego `Actions > ATLAS IA - simulacion bursatil > Run workflow > main`.
4. Abrir trabajo `run` > `Ejecutar motor ficticio`. Buscar `term_deposit_status`, `conservative_status`, `warnings`.
5. En Supabase, ejecutar la consulta de comprobación:

```sql
select id,bank,principal,tea_pct,started_at,maturity_at,status
from public.atlas_term_deposits order by started_at desc limit 10;
```

6. Confirmar una fila `ACTIVE` solamente si la API oficial reportó una TEA y el motor creó el depósito. Si no se creó, el motivo debe aparecer en `term_deposit_status` y `CONSERVATIVE_REVIEW` de la Auditoría. **No forzar números de tasas ni confirmar como ejecutado un producto que no se pudo simular.**
7. Abrir `https://michelvenier.github.io/atlas-ia/` y recargar con Ctrl+F5. Aparece panel `Alternativa conservadora: plazo fijo` y el detalle en la cartera.

Una prueba local de funciones no equivale a una operación real en tu Supabase. La operación autónoma debe verificarse con los registros persistentes del servidor y su próxima ejecución programada.
