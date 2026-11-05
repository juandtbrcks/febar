# Evidence · AI/BI Dashboard

_Captured 2026-11-05 13:55 CST. The dataset SQL below is taken from the dashboard definition (`workspace_export/dashboard.lvdash.json`) and executed on the warehouse; global-filter parameters set to 'all'._

Published: revision 2026-11-05T19:25:56.759Z · embed_credentials=False (viewers see data with their own permissions)

Pages: Cartera y Rentabilidad, Siniestros y Fraude, Comercial y Canales, Reservas (Actuarial), Global Filters

## Dataset `ds_kpi_cartera` (ds_kpi_cartera)

```sql
SELECT ROUND(MEASURE(`Prima Emitida`),0) prima_emitida, ROUND(MEASURE(`Prima Devengada`),0) prima_devengada, MEASURE(`Pólizas Vigentes`) vigentes, ROUND(MEASURE(`Siniestralidad %`)*100,1) siniestralidad, ROUND(MEASURE(`Frecuencia`)*100,1) frecuencia, ROUND(MEASURE(`Severidad`),0) severidad FROM demo_catalog.seguros_demo.mv_cartera_rentabilidad WHERE TRUE AND TRUE AND TRUE
```

| prima_emitida | prima_devengada | vigentes | siniestralidad | frecuencia | severidad |
|---|---|---|---|---|---|
| 1995071830 | 1.760100882E9 | 16188 | 55.7 | 31.3 | 35455 |

## Dataset `ds_kpi_sin` (ds_kpi_sin)

```sql
SELECT MEASURE(`Siniestros`) siniestros, ROUND(MEASURE(`Costo Incurrido`),0) incurrido, ROUND(MEASURE(`Reserva Pendiente`),0) reserva, ROUND(MEASURE(`Tasa de Fraude`)*100,1) tasa_fraude, ROUND(MEASURE(`Monto Fraude Detectado`),0) fraude_detectado, ROUND(MEASURE(`Monto en Riesgo de Fraude`),0) monto_riesgo FROM demo_catalog.seguros_demo.mv_siniestros_fraude WHERE TRUE AND TRUE
```

| siniestros | incurrido | reserva | tasa_fraude | fraude_detectado | monto_riesgo |
|---|---|---|---|---|---|
| 27644 | 980122957 | 115666601 | 6.9 | 145611721 | 7185593.0 |

## Dataset `ds_kpi_com` (ds_kpi_com)

```sql
SELECT MEASURE(`Cotizaciones`) cotizaciones, ROUND(MEASURE(`Tasa de Conversión`)*100,1) conversion, ROUND(MEASURE(`Prima Emitida (convertidas)`),0) prima, ROUND(MEASURE(`Prima Cotizada Promedio`),0) prima_prom FROM demo_catalog.seguros_demo.mv_comercial_canales WHERE TRUE AND TRUE
```

| cotizaciones | conversion | prima | prima_prom |
|---|---|---|---|
| 280201 | 17.9 | 996833834 | 22811 |

## Dataset `ds_kpi_res` (ds_kpi_res)

```sql
SELECT ROUND(MEASURE(`Pagado`),0) pagado, ROUND(MEASURE(`Reserva de Caso`),0) caso, ROUND(MEASURE(`Reserva Requerida`),0) requerida, ROUND(MEASURE(`Suficiencia de Reserva`),0) suficiencia, ROUND(MEASURE(`Suficiencia %`)*100,1) suficiencia_pct FROM demo_catalog.seguros_demo.mv_reservas_actuariales WHERE TRUE
```

| pagado | caso | requerida | suficiencia | suficiencia_pct |
|---|---|---|---|---|
| 858333191 | 116451348 | 7.1782452E7 | 4.4668896E7 | 62.2 |

## Dataset `ds_res_cob` (ds_res_cob)

```sql
SELECT cobertura, tipo, monto FROM (SELECT `Cobertura` cobertura, ROUND(MEASURE(`Reserva de Caso`),0) caso, ROUND(MEASURE(`Reserva Requerida`),0) req FROM demo_catalog.seguros_demo.mv_reservas_actuariales WHERE TRUE GROUP BY 1) UNPIVOT (monto FOR tipo IN (caso AS `Reserva de caso constituida`, req AS `Reserva requerida (chain-ladder)`)) ORDER BY cobertura
```

| cobertura | tipo | monto |
|---|---|---|
| Cristales | Reserva de caso constituida | 164256.0 |
| Cristales | Reserva requerida (chain-ladder) | 105500.0 |
| Daños Materiales | Reserva de caso constituida | 2.8558765E7 |
| Daños Materiales | Reserva requerida (chain-ladder) | 1.958882E7 |
| Gastos Médicos Ocupantes | Reserva de caso constituida | 1.4566913E7 |
| Gastos Médicos Ocupantes | Reserva requerida (chain-ladder) | 1.1265114E7 |
| Responsabilidad Civil | Reserva de caso constituida | 4.883319E7 |
| Responsabilidad Civil | Reserva requerida (chain-ladder) | 3.2705447E7 |
| Robo Total | Reserva de caso constituida | 2.4328224E7 |
| Robo Total | Reserva requerida (chain-ladder) | 8117571.0 |
