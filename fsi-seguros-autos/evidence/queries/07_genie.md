# Evidence · Genie (natural-language queries over governed metric views)

_Captured 2026-11-05 13:52 CST from the live workspace (REST APIs). Values are the real API output._

Genie space `<ID>` queried through the Genie Conversation API with the user's identity (same code path as the app's 'Pregunta a Genie' tab, `agente/app/genie_uc.py`).

## Q: ¿Cuál es la siniestralidad por paquete y cuál es el más rentable?

Status: `COMPLETED`

> El paquete **más rentable es Amplia Plus**, porque tiene la **menor siniestralidad: 44.7%**; el análisis considera todos los paquetes con valor informado. Ejemplos incluyen:
> - **Amplia Plus**: siniestralidad de **44.7%**, con prima emitida de **MXN 118.9M** y costo incurrido de **MXN 46.6M**
> - **Plataformas**: **50.0%**, con prima emitida de **MXN 425.2M** y costo incurrido de **MXN 187.1M**
> - **Limitada**: **51.7%**, con prima emitida de **MXN 241.0M** y costo incurrido de **MXN 110.1M**
> - **Flotilla**: **53.3%**, con prima emitida de **MXN 156.8M** y costo incurrido de **MXN 74.1M**
> - **RC**: **60.0%**, con prima emitida de **MXN 36.8M** y costo incurrido de **MXN 19.5M**
> 
> En los 6 paquetes, la siniestralidad va de **44.7%** a **60.5%**, y **Amplia** es el menos rentable con **60.5%**.

Generated SQL:
```sql
SELECT
  `Paquete`,
  MEASURE(`Prima Emitida`) AS `prima_emitida`,
  MEASURE(`Costo Incurrido`) AS `costo_incurrido`,
  MEASURE(`Siniestralidad %`) AS `siniestralidad`
FROM `demo_catalog`.`seguros_demo`.`mv_cartera_rentabilidad`
WHERE `Paquete` IS NOT NULL
GROUP BY ALL
ORDER BY `siniestralidad` ASC, `prima_emitida` DESC
```

Result:

| Paquete | prima_emitida | costo_incurrido | siniestralidad |
|---|---|---|---|
| Amplia Plus | 118936826.70 | 46610445.41 | 0.44718157423409777 |
| Plataformas | 425214616.49 | 187086526.54 | 0.5004115742685025 |
| Limitada | 240993748.46 | 110093521.46 | 0.5167164815634057 |
| Flotilla | 156841026.80 | 74143771.83 | 0.532702004416036 |
| RC | 36792980.44 | 19487961.99 | 0.599978242618484 |
| Amplia | 1016292631.45 | 542700730.21 | 0.6048322090803557 |

## Q: ¿Qué tanto confirma el SIU los siniestros que el modelo marca como riesgo alto?

Status: `COMPLETED`

> El SIU confirma **21 de 49 casos cerrados** que el modelo marcó con **nivel de riesgo alto**, lo que equivale a una **tasa de confirmación de 42.9%**. Con ese filtro, la **probabilidad media al abrir** fue de **48.3%** y el **monto evitado** en los **21 fraudes confirmados** suma **MXN 1,191,809.25**.

Generated SQL:
```sql
SELECT COUNT(*) AS `casos_cerrados`, SUM(`fraude`) AS `fraudes_confirmados`, AVG(CAST(`fraude` AS DOUBLE)) AS `tasa_confirmacion`, AVG(CAST(`prob_fraude_apertura` AS DOUBLE)) AS `prob_media_modelo`, SUM(CASE WHEN `fraude` = 1 THEN `monto_en_riesgo` ELSE 0 END) AS `monto_evitado` FROM `demo_catalog`.`seguros_siu_expediente`.`etiquetas_siu` WHERE `nivel_riesgo_apertura` IS NOT NULL AND `nivel_riesgo_apertura` ILIKE '%alto%'
```

Result:

| casos_cerrados | fraudes_confirmados | tasa_confirmacion | prob_media_modelo | monto_evitado |
|---|---|---|---|---|
| 49 | 21 | 0.42857142857142855 | 0.4829040816326531 | 1191809.25 |

## Q: ¿En qué tipos de taller se concentra el fraude?

Status: `COMPLETED`

> El fraude se concentra principalmente en **Sin taller** y **talleres Independientes**, que encabezan el monto detectado. En los **4 tipos de taller** analizados, **Sin taller** registra **MXN 65.86M** y **317** fraudes confirmados, mientras **Independiente** muestra la **mayor tasa de fraude** con **12.86%**, además de **853** fraudes confirmados y **MXN 51.36M** detectados.
> 
> Como referencia, **Multimarca** y **Agencia** quedan muy por debajo en monto detectado, con **MXN 14.31M** y **MXN 14.08M**, respectivamente, lo que refuerza que la concentración está en los dos primeros tipos.

Generated SQL:
```sql
SELECT
  `Tipo de Taller`,
  MEASURE(`Siniestros`) AS `siniestros`,
  MEASURE(`Fraudes Confirmados`) AS `fraudes_confirmados`,
  MEASURE(`Tasa de Fraude`) * 100 AS `tasa_fraude_pct`,
  MEASURE(`Monto Fraude Detectado`) AS `monto_fraude_detectado`,
  MEASURE(`Siniestros Alto Riesgo`) AS `siniestros_alto_riesgo`,
  MEASURE(`Presupuesto Taller vs Autorizado`) * 100 AS `presupuesto_vs_autorizado_pct`
FROM `demo_catalog`.`seguros_demo`.`mv_siniestros_fraude`
WHERE `Tipo de Taller` IS NOT NULL
GROUP BY ALL
ORDER BY `monto_fraude_detectado` DESC, `tasa_fraude_pct` DESC, `fraudes_confirmados` DESC
```

Result:

| Tipo de Taller | siniestros | fraudes_confirmados | tasa_fraude_pct | monto_fraude_detectado | siniestros_alto_riesgo | presupuesto_vs_autorizado_pct |
|---|---|---|---|---|---|---|
| Sin taller | 3831 | 317 | 9.542444310656231 | 65858789.23 | 49 | nan |
| Independiente | 7591 | 853 | 12.8638214447293 | 51360465.64 | 67 | 136.9339038955 |
| Multimarca | 8255 | 257 | 3.612594883328648 | 14312979.19 | 19 | 112.0423519305 |
| Agencia | 7967 | 233 | 3.398978847556528 | 14079487.03 | 32 | 112.0380072099 |

## Q: ¿Cuántos casos SIU hay por estatus?

Status: `COMPLETED`

> Hay **4 estatus** con casos SIU registrados (solo se consideraron registros con estatus no nulo). Los casos por estatus son:
> - **Cerrado - Procedente:** **66**
> - **En investigación:** **45**
> - **Abierto:** **26**
> - **Cerrado - Fraude confirmado:** **23**
> El estatus más frecuente es **Cerrado - Procedente** y el menos frecuente es **Cerrado - Fraude confirmado**.

Generated SQL:
```sql
SELECT `estatus`, COUNT(*) AS `casos`
FROM `demo_catalog`.`seguros_siu_expediente`.`casos`
WHERE `estatus` IS NOT NULL
GROUP BY `estatus`
ORDER BY `casos` DESC, `estatus` ASC
```

Result:

| estatus | casos |
|---|---|
| Cerrado - Procedente | 66 |
| En investigación | 45 |
| Abierto | 26 |
| Cerrado - Fraude confirmado | 23 |

## Q: ¿Y solo en la región Centro? _(follow-up in the same conversation)_

Status: `COMPLETED`

> En la **región Centro**, los casos SIU se distribuyen en **4 estatus** y el mayor volumen está en **Cerrado - Procedente** con **26 casos**. Le siguen **En investigación** con **14**, **Cerrado - Fraude confirmado** con **7** y **Abierto** con **6**; en total, son **53 casos** y predominan claramente los casos ya cerrados como procedentes.

Generated SQL:
```sql
SELECT
  `estatus`,
  COUNT(*) AS `casos`
FROM `demo_catalog`.`seguros_siu_expediente`.`casos`
WHERE `region` IS NOT NULL
  AND `estatus` IS NOT NULL
  AND `region` ILIKE '%Centro%'
GROUP BY `estatus`
ORDER BY `casos` DESC, `estatus` ASC
```

Result:

| estatus | casos |
|---|---|
| Cerrado - Procedente | 26 |
| En investigación | 14 |
| Cerrado - Fraude confirmado | 7 |
| Abierto | 6 |

## Q: ¿Nuestras reservas son suficientes? ¿En qué cobertura sobra o falta?

Status: `COMPLETED`

> Sí: en las **5 coberturas** mostradas, la **reserva de caso supera la reserva requerida**, así que no hay faltantes en este resultado. Algunos ejemplos son:
> - **Cristales**: sobra **MXN 58,756** (**55.7%** por encima de lo requerido)
> - **Gastos Médicos Ocupantes**: sobra **MXN 3.30M** (**29.3%**)
> - **Daños Materiales**: sobra **MXN 8.97M** (**45.8%**)
> - **Responsabilidad Civil**: sobra **MXN 16.13M** (**49.3%**)
> - **Robo Total**: sobra **MXN 16.21M** (**199.7%**)
> Como insight, la mayor holgura relativa está en **Robo Total**, mientras que la menor está en **Gastos Médicos Ocupantes**, por lo que ahí es donde las reservas están más ajustadas dentro de lo observado.

Generated SQL:
```sql
SELECT
  `Cobertura`,
  MEASURE(`Reserva de Caso`) AS `reserva_caso`,
  MEASURE(`Reserva Requerida`) AS `reserva_requerida`,
  MEASURE(`Suficiencia de Reserva`) AS `suficiencia_reserva`,
  MEASURE(`Suficiencia %`) AS `suficiencia_pct`,
  MEASURE(`% Desarrollado`) AS `pct_desarrollado`
FROM `demo_catalog`.`seguros_demo`.`mv_reservas_actuariales`
WHERE `Cobertura` IS NOT NULL
GROUP BY ALL
ORDER BY `suficiencia_reserva` ASC
```

Result:

| Cobertura | reserva_caso | reserva_requerida | suficiencia_reserva | suficiencia_pct | pct_desarrollado |
|---|---|---|---|---|---|
| Cristales | 164256.29 | 105500.05 | 58756.24 | 0.5569309208858194 | 0.9935378051663636 |
| Gastos Médicos Ocupantes | 14566913.08 | 1.12651138E7 | 3301799.28 | 0.2930995051288341 | 0.8344774221600112 |
| Daños Materiales | 28558765.23 | 1.958882038E7 | 8969944.85 | 0.45791143499167664 | 0.9530469103139483 |
| Responsabilidad Civil | 48833190.06 | 3.270544682E7 | 1.612774324E7 | 0.4931210183050482 | 0.8131082159974509 |
| Robo Total | 24328223.70 | 8117571.12 | 1.621065258E7 | 1.9969831296039202 | 0.9679825095340251 |
