# FSI — Reservas actuariales (chain-ladder) · guion del demo

**Dónde vive:** sección *Actuarial* al final de `pipeline2_star.sql` (pipeline maestro `seguros_medallion`), metric view
`mv_reservas_actuariales` (`semantica/metric_views.sql`), página **Reservas (Actuarial)** del dashboard y Genie.

## Tablas
| Tabla | Qué es |
|---|---|
| `act_triangulo_observado` | *Privada del pipeline* (no se publica): pagado/incurrido acumulado por cobertura × periodo × edad |
| `act_factores_desarrollo` | Factor edad-a-edad (12→24, 24→36…) y factor a último por cobertura |
| `act_reservas` | Por cobertura × periodo: pagado, reserva de caso, último estimado, reserva requerida, IBNR, suficiencia |
| `act_triangulo` | Triángulo completado (celdas observadas + proyectadas) |
| `act_siniestralidad_periodo` | Siniestralidad reportada vs última por periodo, con prima devengada |

## Convenciones
- **Valuación 30-sep-2026.** Periodos de ocurrencia de 12 meses **oct–sep** (2026 = oct-2025 a sep-2026), para que cada
  diagonal sea una evaluación completa a 12, 24, 36… meses y no se proyecten accidentes que aún no ocurren.
- Montos netos de recuperaciones. Pagado = pagos − recuperaciones; incurrido = pagado + reserva de caso.
- Factores ponderados por volumen, sin factor de cola (los pagos de RC terminan antes de 60 meses).

## Cifras (valuación 2026-09-30)
- Reserva de caso constituida **$116.5M** vs requerida por chain-ladder **$71.8M** → **suficiencia $44.7M (62%)**.
- $11.8M de reserva de caso están en siniestros abiertos con riesgo **Alto** de fraude (modelo @champion).
- Colas: RC factor a último desde 12m = 3.24, GMO 2.63, Daños Materiales 1.32, Robo 1.22, Cristales 1.04.
- Último periodo: siniestralidad reportada **64.1%** vs última estimada **54.1%**.

## Guion (5 min)
1. **El problema** — "Un siniestro no se paga en un día: RC y gastos médicos se pagan durante 2–3 años, y hay accidentes que
   nadie ha reportado aún. ¿Cuánto debo reservar hoy?" Hoy los actuarios tardan ~10 h juntando extractos del DWH.
2. **Triángulo** (tabla del dashboard) — filas = periodo de ocurrencia, columnas = edad. Arriba-izquierda es historia;
   las celdas con ▸ son el futuro estimado. Sale de `fact_movtos_siniestro`, la MISMA tabla gobernada que usan el tablero y el
   modelo de fraude: sin extractos, con linaje.
3. **Patrón de pago** (línea) — Cristales/Daños se pagan casi todo en 12 meses; RC/GMO tienen cola larga.
4. **Suficiencia** (KPIs + barras) — la reserva de caso está $45M arriba de lo que el método estima: capital inmovilizado.
   Gancho con fraude: $11.8M de esa reserva están en siniestros que el modelo marca como Alto riesgo.
5. **Siniestralidad reportada vs última** — el periodo más reciente "se ve" en 64% pero terminará en ~54%: decisiones de
   tarifa/suscripción sobre el número correcto.
6. **Genie** — "¿Nuestras reservas son suficientes? ¿En qué cobertura sobra o falta?" / "¿A cuánto llegará la siniestralidad
   del último periodo?"

**Honestidad:** los datos son sintéticos; el generador fija reservas iniciales conservadoras (~1.1× reclamado vs ~0.85×
pagado), por eso el IBNR sale negativo. Chain-ladder es el método base; en producción se complementa con
Bornhuetter-Ferguson, incurred chain-ladder y métodos regulatorios CNSF.
