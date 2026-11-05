# FSI — Bloque de Gobierno ("no extractos")

Notebooks en `/Workspace/Users/<tu_usuario>/seguros_demo/gobierno/`. Warehouse `seguros-demo-wh`.

| Script | Qué hace | ¿Se ejecuta en el demo? |
|---|---|---|
| `01_roles_funciones.sql` | Schema `seguros_gobierno`, tabla `usuarios_rol`, funciones `rol_actual()`, `mask_*`, `filtro_region` | Ya aplicado |
| `02_tags_politicas.sql` | Governed tags (`seguros_pii`, `seguros_region`, `seguros_certificacion`) en ~70 columnas/tablas + 7 políticas ABAC | Ya aplicado (re-ejecutar tras *full refresh*) |
| `03_demo_personas.sql` | **Demo en vivo**: misma consulta con roles SIU → Actuario → Gerente Norte | Sí |
| `04_permisos.sql` | **Plantilla** del modelo de mínimo privilegio (requiere grupos de cuenta `seguros_*`) | Solo se muestra |
| `05_auditoria.sql` | Auditoría y linaje: accesos, descargas, cambios de gobierno, conexiones nuevas, copias | Sí |

## Guion sugerido (≈10 min)

1. **Catalog Explorer → `dim_cliente`**: mostrar los tags `seguros_pii` en columnas y `seguros_certificacion = oficial` en la tabla.
   `bronze_cliente_consolidado_2011` aparece como `legacy_no_usar`. Mensaje: *la PII está identificada en todas las capas*.
2. **Políticas ABAC** (pestaña *Policies* del schema `seguros_demo`): una regla por tipo de PII + filtro por región.
   Se escriben una vez y aplican solas a cualquier tabla oficial nueva con la columna etiquetada.
3. **`03_demo_personas`**: misma consulta, tres resultados:
   - SIU: 60,000 clientes, PII completa.
   - Actuario/BI: 60,000 clientes, `P. O. E.` / `OEEP*********` / `***@***`.
   - Gerente Norte: **10,655** clientes (solo su región), PII parcial; `fact_siniestros` solo Norte.
4. **"¿Y si copio la tabla?"**: `seguros_sandbox_ds.copia_clientes_ana` se creó como ACTUARIO con
   `CREATE TABLE AS SELECT`; la copia quedó **enmascarada para siempre**, ni el SIU puede recuperar la PII desde ahí.
5. **Permisos (`04_permisos`)**: consumo solo `SELECT` en oro; bronce/plata y fuentes federadas solo ingeniería;
   nadie de consumo puede `CREATE TABLE` en el schema oficial; ciencia de datos tiene sandbox propio.
   Crear conexiones a Oracle es privilegio del metastore → nadie re-ingesta la fuente por su cuenta.
6. **Cerrar la salida** (mostrar en *Settings → Security* del workspace, **no cambiar**: el workspace es compartido):
   deshabilitar descarga de resultados en SQL, notebooks y dashboards; controles de egress de serverless.
7. **`05_auditoria`**: quién consultó qué, intentos de descarga/exportación, cambios de políticas/tags,
   conexiones nuevas y el linaje que delata la copia de "Ana" (`dim_cliente` → `copia_clientes_ana`).

## Notas operativas

- **Rol del presentador**: dejarlo en `SIU` al terminar (`03_demo_personas` lo hace en su última celda).
  Cualquier otro usuario del workspace sin fila en `usuarios_rol` ve el rol por omisión `ACTUARIO` (PII enmascarada).
- **Pipelines y masking**: las políticas solo aplican a tablas `oficial` (oro). Plata/bronce se protegen con permisos,
  así los pipelines (que corren como el dueño) nunca leen datos enmascarados.
- **Latencia**: `system.access.audit` y `system.access.table_lineage` tardan de minutos a ~1 h; revisar
  `05_auditoria` antes del demo.
- **Full refresh** de `seguros_medallion` (o recrear tablas oro) puede perder tags: re-ejecutar `02_tags_politicas.sql` (+ tags manuales `sensibilidad`/`chaneltag`, ver `migracion_medallion/reaplicar_tags_oro.sql`).
