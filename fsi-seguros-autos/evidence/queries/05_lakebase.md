# Evidence · Lakebase operational serving

_Captured 2026-11-05 13:50 CST with psql against Lakebase project `seguros-siu`, database `siu` (OAuth identity). Output below is the real psql output._

## Synced table status (reverse ETL from Delta)
```text
synced_table: seguros_siu_lakebase.serving.bandeja_siu
state: SYNCED_TABLE_ONLINE_NO_PENDING_UPDATE
source: demo_catalog.seguros_ml.bandeja_siu_serving
pipeline_id: <UUID>
```

## Row counts: Delta source vs Lakebase synced table
```text
  delta_rows
  3722
 lakebase_rows |         last_scoring          
---------------+-------------------------------
          3722 | 2026-10-15 23:16:26.310808+00
(1 row)

```

## Operational case file written by investigators and the app
```text
           estatus           | casos 
-----------------------------+-------
 Abierto                     |    26
 Cerrado - Fraude confirmado |    23
 Cerrado - Procedente        |    66
 En investigación            |    45
(4 rows)

      tipo      | notas 
----------------+-------
 cambio_estatus |    89
 nota           |   295
(2 rows)

           autor            | tipo |     texto     |             fecha             
----------------------------+------+---------------+-------------------------------
 <tu_usuario> | nota | si estuvo mal | 2026-11-05 17:43:27.775151+00
(1 row)

 checkpoints_agente 
--------------------
                 10
(1 row)

          usuario           |                           titulo                            |          actualizada          | aprobacion_pendiente 
----------------------------+-------------------------------------------------------------+-------------------------------+----------------------
 <tu_usuario> | ¿Qué 5 siniestros debo revisar primero en la región Centro? | 2026-11-05 17:43:42.709829+00 | f
(1 row)

                                List of tables
 Schema |         Name          | Type  |                Owner                 
--------+-----------------------+-------+--------------------------------------
 agente | checkpoint_blobs      | table | <UUID>
 agente | checkpoint_migrations | table | <UUID>
 agente | checkpoint_writes     | table | <UUID>
 agente | checkpoints           | table | <UUID>
 agente | sesiones              | table | <tu_usuario>
(5 rows)

```

## Row-Level Security tests (as an unprivileged role, the way the app connects)
```text
-- Context: AGENTE_REGIONAL, region Norte
BEGIN
SET
         u         |        r        |   g   
-------------------+-----------------+-------
 agente.norte@demo | AGENTE_REGIONAL | Norte
(1 row)

       t        | count | regiones 
----------------+-------+----------
 casos visibles |    37 |        1
(1 row)

        t        | count 
-----------------+-------
 bandeja visible |   679
(1 row)

-- Regional agent tries to open a case (only SIU may):
SAVEPOINT
ERROR:  new row violates row-level security policy for table "casos"
ROLLBACK
-- Regional agent writes a note in another region:
SAVEPOINT
ERROR:  new row violates row-level security policy for table "notas"
ROLLBACK
-- Regional agent signs a note as someone else:
SAVEPOINT
ERROR:  new row violates row-level security policy for table "notas"
ROLLBACK
-- Regional agent writes its own note in its region (allowed):
SAVEPOINT
INSERT 0 1
ROLLBACK
ROLLBACK
-- No context set (default deny):
BEGIN
SET
 bandeja_sin_contexto 
----------------------
                    0
(1 row)

ROLLBACK
-- Context: SIU, all regions
BEGIN
SET
         u         |  r  | g 
-------------------+-----+---
 investigador@demo | SIU | *
(1 row)

       t        | count | regiones 
----------------+-------+----------
 casos visibles |   160 |        6
(1 row)

ROLLBACK
```

## Lakebase → Delta change data feed (closes the loop)
```text
casos                CDF_STATE_STREAMING 2026-11-05T00:18:54.216501Z
notas                CDF_STATE_STREAMING 2026-11-05T17:43:33.944469Z
historial_estatus    CDF_STATE_STREAMING 2026-11-05T00:19:00.993372Z
  t | n
  casos (Delta via CDF) | 160
  notas (Delta via CDF) | 384
  etiquetas_siu (labels for retraining) | 89
casos (Postgres) 160
notas (Postgres) 384
```
