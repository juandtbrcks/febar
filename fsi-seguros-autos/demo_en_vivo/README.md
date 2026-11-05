# Demo en vivo — Cuarentena de calidad

1. Mostrar `cuarentena_registros` (748 registros, cada uno con la regla que falló).
2. Soltar el lote "sucio" de la app (4 FNOL: GPS en París y en (0,0), fotos negativas, sin siniestro):
   `databricks fs cp ./demo_en_vivo/fnol_2026-10-13_lote_en_vivo.json dbfs:/Volumes/demo_catalog/seguros_demo/datalake_ds/app_autos/fnol/ -p DEFAULT`
3. Correr el pipeline `seguros_medallion` (botón Start). Auto Loader solo lee el archivo nuevo.
4. Volver a consultar:
   ```sql
   SELECT tabla_destino, llave, reglas_fallidas, registro
   FROM demo_catalog.seguros_demo.cuarentena_registros
   WHERE tabla_destino = 'silver_app_fnol' ORDER BY fecha_deteccion DESC;
   ```
   → 12 en cuarentena de la app (8 + 4). Mensaje: "nada se pierde en silencio; cada descarte queda explicado".
   Mencionar: en producción se agrega una conciliación automática por tabla (origen = destino + cuarentena) como control de auditoría.

**Para resetear después del demo:** `databricks fs rm dbfs:/Volumes/demo_catalog/seguros_demo/datalake_ds/app_autos/fnol/fnol_2026-10-13_lote_en_vivo.json -p DEFAULT`
y full refresh de `bronze_app_fnol` + `silver_app_fnol` (streaming tables conservan lo ya leído).

**Notas:**
- `pipeline3_cuarentena.sql` es GENERADO por `gen_cuarentena.py` desde las expectations DROP de plata (las reglas viven en un solo lugar).
  Si cambias una regla de plata: `python3 gen_cuarentena.py` y volver a subir el notebook (la conciliación automática se quitó del demo para simplificar el grafo; para verificar a mano: bronce − plata = cuarentena por tabla).
- Semántica: una regla que evalúa a NULL cuenta como FALLA (así se comportan las expectations) → `COALESCE(cond, FALSE)`.
- Datos sucios en PG: `inyectar_sucios_pg.py` (idempotente; `--borrar` los quita). IDs: clientes/siniestros/recibos/créditos 9,000,000+, pólizas 90,000,000+.
