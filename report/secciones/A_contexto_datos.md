# Borrador de secciones del informe: Nelson Escalante

Corresponde a las secciones 2 (problema y escenario real) y 4 (datos, protocolo, procedencia y partición) del índice del plan, más las limitaciones de medición para la sección 11. Los marcadores **[COMPLETAR]** dependen del montaje y de las mediciones; no se rellenan con valores supuestos.

---

## 2. Problema, escenario real, pregunta y objetivos

### 2.1 Contexto

Regar macetas con un horario y una dosis fijos es sencillo, pero no responde a cuánta agua perdió realmente cada maceta. Con poca pérdida, una parte del agua sale como drenaje y se desperdicia; con mucha, el sustrato puede quedar demasiado seco antes del riego siguiente. Medir el peso de la maceta permite estimar esa pérdida sin sensores: entre dos pesajes sin riego, la disminución de masa se debe casi por completo al agua evaporada y transpirada.

El riego guiado por mediciones se ha estudiado antes. Lieth [R1] comparó, en invernaderos comerciales de California, un riego activado por tensiómetros con el riego del productor y con un riego temporizado. Reportó el agua aplicada por maceta en mL/día en ocho experimentos con crisantemo, flor de pascua, gerbera e hidrangea. Kombala Liyanage et al. [R2] describen un método gravimétrico semiautomatizado que usa el peso de la maceta para controlar el agua del sustrato. Ninguna de las dos fuentes reproduce nuestro montaje (especie, sustrato, clima y escala distintos), así que se usan como antecedente del método y de la métrica, no para validar el modelo.

### 2.2 Sistema estudiado

| Elemento | Descripción |
| --- | --- |
| Sistema | Seis macetas de [COMPLETAR: especie] en [COMPLETAR: sustrato], ubicadas en [COMPLETAR: lugar], protegidas de lluvia |
| Actores | Integrantes del equipo que pesan, riegan y registran en turnos de tres revisiones diarias |
| Entradas | Agua aplicada en cada riego (mL); condiciones ambientales no controladas (agrupadas en la pérdida `E`) |
| Estado | Déficit `D` respecto de la masa drenada de referencia (mL) |
| Salidas | Masa de la maceta (g), drenaje (mL) |
| Decisión | Cuánto regar en cada revisión |
| Métrica principal | Agua total aplicada por maceta en el horizonte (mL/maceta), a **minimizar**, con el déficit dentro del intervalo operacional |

### 2.3 Pregunta de investigación

¿Puede una política de riego optimizada reducir el agua aplicada por maceta, respecto de un horario fijo razonable, manteniendo el déficit de agua dentro de un intervalo operacional justificado y bajo las condiciones observadas?

### 2.4 Alcance

Incluye una especie, un sustrato y un tipo de recipiente, pérdida conjunta por evaporación y transpiración, y riego manual en horarios fijos de revisión. Excluye automatización, crecimiento y salud de la planta, flujo espacial de agua en el sustrato y generalización a otras especies o estaciones. Mantener el déficit en un intervalo **no** demuestra bienestar fisiológico; el intervalo se justifica con [COMPLETAR: fuente sobre la especie] y con el piloto.

---

## 4. Datos, protocolo, procedencia y partición

### 4.1 Procedencia

Todos los datos usados para calibrar y validar son **observaciones propias** del equipo (`data_origin = observed`), tomadas entre [COMPLETAR: fecha inicio] y [COMPLETAR: fecha fin] en [COMPLETAR: lugar]. Los datos sintéticos del repositorio (`data/synthetic/`) solo prueban el código; están marcados como tales y no aparecen en ninguna tabla de validación.

| Conjunto | Período | Macetas | Lecturas utilizables | Riegos |
| --- | --- | --- | --- | --- |
| Piloto | [COMPLETAR] | 6 | [COMPLETAR] | [COMPLETAR] |
| Ajuste | [COMPLETAR] | 6 | [COMPLETAR] | [COMPLETAR] |
| Validación | [COMPLETAR] | 6 | [COMPLETAR] | [COMPLETAR] |

### 4.2 Protocolo

Resumen de `docs/protocol.md`:

1. **Balanza.** Se pesó [COMPLETAR] veces un objeto estable. Desviación de repetibilidad: [COMPLETAR] g; resolución: [COMPLETAR] g; error por lectura `σ_lectura` = [COMPLETAR] g.
2. **Referencia drenada.** Cada maceta se regó hasta drenar y se pesó durante el drenaje. La masa se estabilizó a los [COMPLETAR] min (mediana), y ese tiempo se fijó en [COMPLETAR] min. `M_ref` va de [COMPLETAR] a [COMPLETAR] g.
3. **Revisiones** a las [COMPLETAR] h. Pesaje sin riego, o pesaje antes del riego, riego medido, drenaje durante el tiempo fijado y pesaje posterior.
4. **Registro** en CSV con fecha y zona horaria, observador y marca de calidad. Los faltantes quedan faltantes y los originales no se modifican.

### 4.3 Variable observada

$$D(t) = \frac{M_{ref} - M(t)}{\rho_w}, \qquad \rho_w \approx 1\ \text{g/mL}$$

Interpretar `D` como agua requiere suponer que el resto de la masa (maceta, sustrato seco, planta) no cambia durante el período analizado. [COMPLETAR: evidencia de deriva por crecimiento o caída de hojas, o su ausencia.]

### 4.4 Control de calidad

`validate-data` aplica las comprobaciones de `docs/data_dictionary.md`. Resultado: [COMPLETAR: n errores corregidos antes de calibrar, n advertencias y su tipo]. Lecturas excluidas (`bad`): [COMPLETAR] por [COMPLETAR: motivos].

### 4.5 Partición ajuste/validación

Los datos se dividieron por **ventanas de tiempo completas**, nunca por filas sueltas, para no filtrar información entre lecturas consecutivas. La partición se congeló el [COMPLETAR] (`configs/data.json`), antes del ajuste final. El código rechaza lecturas cuya fase no coincida con su ventana, y el ajuste rechaza cualquier intervalo fuera de la fase de ajuste. Las lecturas de validación no se usaron para elegir parámetros del modelo ni de PSO.

### 4.6 Calibración de la pérdida de agua

Se usaron [COMPLETAR] intervalos de secado de la fase de ajuste ([COMPLETAR] días). El método está en `docs/calibration.md`: solución exacta por tramos, mínimos cuadrados y selección del modelo más simple con AICc a menos de 2 del mínimo.

**Tabla A1.** Comparación de modelos (de `results/tables/seleccion_modelos.csv`).

| Modelo | k | RMSE (mL) | ΔAICc | Seleccionado |
| --- | --- | --- | --- | --- |
| constant | 1 | [COMPLETAR] | [COMPLETAR] | |
| blocks | 2 | [COMPLETAR] | [COMPLETAR] | |
| blocks_linear | 3 | [COMPLETAR] | [COMPLETAR] | |

**Tabla A2.** Parámetros (de `results/tables/parametros.csv`).

| Parámetro | Valor | Unidad | IC 95 % (bootstrap por días) | Origen |
| --- | --- | --- | --- | --- |
| `a` | [COMPLETAR] | mL/h | [COMPLETAR] | Ajuste, fase fit |
| `b` | [COMPLETAR] | 1/h | [COMPLETAR] | Ajuste o fijado en 0 |
| `q_noche` | [COMPLETAR] | — | [COMPLETAR] | Ajuste |
| `σ_lectura` | [COMPLETAR] | g | — | Verificación de balanza |
| `ρ_w` | 1 | g/mL | — | Supuesto |
| Rango de `D` en ajuste | [COMPLETAR] | mL | — | Observado; límite de extrapolación |

### 4.7 Respuesta al riego

En los [COMPLETAR] riegos de piloto y ajuste, el drenaje observado menos el ideal (`max(0, I − D⁻)`) tuvo media [COMPLETAR] mL y desviación [COMPLETAR] mL. [COMPLETAR: interpretación. ¿Se sostiene el drenaje instantáneo dentro del error de medición o hace falta un estado de agua excedente?]

---

## 11 (aporte). Limitaciones de medición

- **Resolución y repetibilidad de la balanza.** Cambios menores que unas pocas `σ_lectura` no se distinguen del ruido.
- **Pocas plantas.** Seis macetas en tres pares forman un piloto, no una prueba agronómica. Muchas lecturas de una maceta no son plantas independientes.
- **Pocos días independientes.** Los intervalos de un mismo día comparten clima; por eso la incertidumbre se calcula remuestreando días. Con [COMPLETAR] días, los intervalos de confianza son aproximados.
- **Deriva de masa.** El crecimiento o la caída de hojas cambian la masa sin cambiar el agua.
- **Frecuencia de pesaje.** Con tres lecturas al día no se conoce con exactitud cuánto tiempo pasó el déficit sobre un límite.
- **Referencia operacional.** `M_ref` depende del tiempo de drenaje elegido; no es capacidad de campo.
- **Condiciones.** Los resultados valen para la especie, el sustrato, el lugar y la época observados ([COMPLETAR]); no se extrapolan a otras estaciones ni especies.

## Referencias citadas en estas secciones

- [R1] Lieth, H. *Tensiometer-based irrigation of potted plants*. Environmental Horticulture, University of California, Davis. https://lieth.ucdavis.edu/research/tens/96/potirg.htm (consultado el 2026-11-03).
- [R2] Kombala Liyanage, D., Chathuranga, I., Mori, B. A., y Thilakarathna, M. S. (2022). A Simple, Semi-Automated, Gravimetric Method to Simulate Drought Stress on Plants. *Agronomy*, 12(2), 349. https://doi.org/10.3390/agronomy12020349
- [COMPLETAR] Fuente sobre el manejo hídrico de la especie elegida.
