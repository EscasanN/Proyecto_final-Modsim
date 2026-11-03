# Protocolo de medición

**Responsable:** Nelson Escalante · **Revisión:** equipo completo · **Estado:** borrador para el piloto; se congela al terminarlo (sección 9).

Este protocolo define cómo se obtienen los datos reales que usan la calibración y la validación del modelo. Los nombres de columnas y los valores permitidos están en [data_dictionary.md](data_dictionary.md). Si cambias el protocolo, registra el cambio en la bitácora (sección 10) con su fecha.

## 1. Objetivo de la medición

Medir, en cada maceta, la masa total antes y después de cada riego, el agua aplicada y el drenaje, para estimar:

- la pérdida de agua entre riegos, `E(t, D)`, en mL/h;
- la respuesta a cada riego (cuánto se retiene y cuánto drena);
- el error de medición, que fija las tolerancias del ajuste y de la validación.

La variable observable es el **déficit respecto de la referencia drenada**, `D = (M_ref − M) / ρw`, en mL, con `ρw ≈ 1 g/mL`. **No** representa humedad volumétrica ni potencial hídrico.

## 2. Montaje

| Elemento | Decisión | Se registra en |
| --- | --- | --- |
| Macetas | 6 (M01–M06), tres pares de plantas similares (P1–P3) | `macetas.csv` |
| Especie y sustrato | Una sola especie, un solo sustrato, un solo tipo de recipiente | `macetas.csv` (`species`, `substrate`) |
| Ubicación | Protegida de lluvia, exposición comparable; anotar cualquier cambio | `macetas.csv` (`location`) y `notes` |
| Bandejas | Una por maceta, removibles; el drenaje no se deja para que la planta lo reabsorba | — |
| Balanza | Identificada (`scale_id`), siempre la misma | `balanza.csv` |
| Dosificación | Probeta o recipiente graduado; confirmar por peso si es posible | `irrigation_ml` |

Etiqueta cada maceta con su `pot_id` en un lugar visible. Pesa siempre el mismo conjunto: **maceta + sustrato + planta, sin bandeja y sin plato**. Si por algún motivo tienes que pesar con plato, anótalo en `notes` y marca `quality_flag = suspect`.

## 3. Verificación de la balanza (antes del piloto y una vez por semana)

1. Coloca la balanza sobre una superficie firme y nivelada, lejos de corrientes de aire. Enciéndela y espera a que se estabilice.
2. Pesa un objeto estable 10 veces seguidas, retirándolo y volviéndolo a poner cada vez. Si tienes una masa conocida (una pesa o un objeto pesado en una balanza de referencia), úsala también.
3. Registra cada lectura en `data/raw/balanza.csv` (una fila por pesaje) con la resolución que muestra la balanza (`resolution_g`).

El código calcula la desviación estándar de repetibilidad, el sesgo frente a la masa conocida y `σ_lectura = sqrt(sd² + resolución²/12)`. A partir de `σ_lectura` se fijan:

- la tolerancia para detectar aumentos de masa sin riego y déficits negativos (`3·√2·σ_lectura`);
- el error de medición que usará el simulador al imitar el pesaje (`D_hat`).

**Criterio de suficiencia:** la pérdida esperada entre dos revisiones consecutivas debe ser al menos 5 veces `σ_lectura`. Si el piloto muestra que no lo es, hay que cambiar de balanza, espaciar las lecturas o usar macetas más grandes (riesgo "balanza insuficiente" del plan).

## 4. Masa de referencia drenada (`M_ref`)

Por cada maceta, una vez al inicio del piloto:

1. Riega lentamente hasta que salga agua por los orificios de drenaje.
2. Deja drenar libremente sobre la bandeja vacía. **No** dejes la maceta en agua estancada.
3. Pesa a los 5, 10, 15, 20 y 30 minutos tras el riego. Registra cada pesaje como `reading_stage = drainage_check`, con el mismo `event_id`, y el último como `post_drainage`, con `irrigation_ml`, `drainage_ml` y la hora real de riego en `irrigation_timestamp`.
4. El **tiempo de drenaje** del protocolo es el primer tiempo a partir del cual las lecturas ya no cambian más que la tolerancia. `calibrate` lo estima (`results/tables/tiempo_drenaje.csv`); el equipo fija un valor común (redondeado hacia arriba) y lo anota en la sección 9.
5. La masa en ese tiempo es `M_ref` de la maceta. Anótala en `macetas.csv` (`reference_mass_g`, `reference_timestamp`).

`M_ref` es una referencia operacional de este montaje, no una capacidad de campo. **No se redefine** durante el experimento. Si la planta crece o pierde hojas de forma notable, se documenta y se discute en el equipo (sección 8); no se ajusta la referencia en silencio.

## 5. Rutina de cada revisión

Horario inicial: **07:00, 13:00 y 19:00** (hora de Guatemala, UTC−06:00). Se ajusta tras el piloto y queda fijo en la sección 9. Registra la **hora real**, no la planeada.

### 5.1 Revisión sin riego

1. Vacía la bandeja si tiene agua y anótalo en `notes`.
2. Pesa la maceta y registra una fila `no_irrigation` con `mass_g`.

### 5.2 Revisión con riego

1. Pesa antes de regar → fila `pre_irrigation` con `mass_g` y un `event_id` nuevo (`M01-E001`, `M01-E002`, …).
2. Mide la dosis, riega y anota la hora real de riego.
3. Espera el tiempo de drenaje fijado, con la maceta sobre la bandeja vacía.
4. Mide el drenaje recogido (mL) y pesa la maceta → fila `post_drainage` con `mass_g`, `irrigation_ml`, `drainage_ml`, `irrigation_timestamp` y el mismo `event_id`.
5. Vacía la bandeja.

El riego y el drenaje se anotan **solo una vez**, en la fila `post_drainage`, para no contarlos dos veces.

### 5.3 Qué hacer si algo sale mal

| Situación | Qué registrar |
| --- | --- |
| No se pudo pesar | La fila con `mass_g` vacío y el motivo en `notes`. No inventar el valor. |
| Se derramó agua o tierra | `quality_flag = suspect` o `bad` y descripción en `notes` |
| Se olvidó medir el drenaje | `drainage_ml` vacío (no cero) y `notes` |
| Lluvia, viento fuerte, maceta movida | `notes` y, si afecta la masa, `quality_flag = suspect` |
| Caída de hojas, poda, plaga | `notes`; avisar a Nelson Escalante para evaluar deriva de masa |
| Balanza con fallas | `quality_flag = bad` en las lecturas afectadas; repetir la verificación (sección 3) |

`quality_flag = bad` excluye la lectura del ajuste; `suspect` la conserva pero queda señalada en los reportes.

## 6. Registro y entrega de datos

1. Anota en papel o en el teléfono durante la revisión; transcribe a `data/raw/observaciones.csv` el mismo día.
2. Fechas en ISO 8601 **con zona horaria**: `2026-11-10T07:05:00-06:00`.
3. Decimales con punto. Cero solo si la cantidad fue **medida** y es cero; un dato faltante se deja vacío.
4. Agrega filas al final; **nunca** sobrescribas ni borres filas existentes. Un error se corrige agregando una nota y la marca de calidad, y se discute con Nelson Escalante.
5. Ejecuta `python -m src.macetas validate-data` antes de hacer commit. No subas datos con errores (código de salida 1).
6. Commit con mensaje `datos: revisión AAAA-MM-DD HH:MM (iniciales)`.

## 7. Turnos

Rotación A (Nelson Escalante) → B → C → D por revisión, continuando la secuencia entre días, incluidos fines de semana. Cada revisión tiene titular y suplente. Completar antes del piloto:

| Fecha | 07:00 titular / suplente | 13:00 titular / suplente | 19:00 titular / suplente |
| --- | --- | --- | --- |
| [COMPLETAR] | | | |

## 8. Partición de datos (ajuste / validación)

- **Piloto** (2–3 días): establecer `M_ref`, tiempo de drenaje, horarios y verificar la balanza. No se usa para ajustar el modelo final.
- **Ajuste** (`fit`): días iniciales posteriores al piloto, con varios ciclos completos de secado y riego.
- **Validación** (`validation`): ciclos posteriores, reservados. No se usan para elegir parámetros del modelo ni de PSO.
- **Intervención** (`intervention`): solo si hay comparación física base/optimizada, después de congelar la política.

La partición se define por ventanas de tiempo completas en `configs/data.json` (`split.windows`), nunca por filas sueltas. Se congela (`frozen: true`, `frozen_on`) **antes** del ajuste final. El código rechaza filas cuya `phase` no coincida con su ventana y el ajuste rechaza intervalos fuera de `fit`.

## 9. Decisiones que se congelan tras el piloto

| Decisión | Valor | Fecha | Justificación |
| --- | --- | --- | --- |
| Especie y sustrato | [COMPLETAR] | | Fuente de manejo: [COMPLETAR] |
| Horarios de revisión | [COMPLETAR] | | |
| Tiempo de drenaje (min) | [COMPLETAR] | | `tiempo_drenaje.csv` |
| `σ_lectura` (g) | [COMPLETAR] | | `parametros.csv` |
| Bloques horarios de `q(t)` | [COMPLETAR] (inicial: día 06–18, noche 18–06) | | `configs/model.json` |
| Ventanas de ajuste y validación | [COMPLETAR] | | `configs/data.json` |
| Tolerancia de validación (MAE, mL) | [COMPLETAR] | | Basada en `σ_lectura` y en la escala de la dosis, fijada antes de ver el error |
| Intervalo operacional y `D_seguro` | [COMPLETAR] | | Fuente específica de la especie + piloto |
| Política base (dosis y horario) | [COMPLETAR] (lo define B) | | |

## 10. Bitácora de cambios del protocolo

| Fecha | Cambio | Motivo | Quién |
| --- | --- | --- | --- |
| 2026-11-03 | Versión inicial | — | Nelson Escalante |
