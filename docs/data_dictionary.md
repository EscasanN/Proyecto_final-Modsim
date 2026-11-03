# Diccionario de datos

**Responsable:** Nelson Escalante. Implementado en `src/macetas/data_io.py`; cualquier cambio aquí debe reflejarse allí y viceversa.

## Reglas generales

- Archivos CSV en UTF-8, separador coma, decimales con punto, una fila por registro.
- Fechas: ISO 8601 **con zona horaria** (`2026-11-10T07:05:00-06:00`). Una fecha sin zona es un error.
- Vacío = **faltante**. Cero solo cuando la cantidad se midió y fue cero.
- Los CSV de `data/raw/` solo se amplían agregando filas. No se sobrescriben, no se ordenan, no se completan con estimaciones.
- `row` en los reportes es el número de línea del CSV (la línea 1 es el encabezado).

## Origen de los datos (`data_origin`)

Obligatorio en los tres archivos. El enunciado exige distinguir datos reales, públicos, estimados y sintéticos.

| Valor | Significado |
| --- | --- |
| `observed` | Medición propia del equipo con este protocolo |
| `public` | Dato publicado por terceros (con referencia en `docs/references.bib`) |
| `estimated` | Valor calculado o supuesto, no medido |
| `synthetic` | Generado por código (pruebas y desarrollo) |

`configs/data.json` solo admite `observed` en `data/raw/`. Los datos sintéticos viven en `data/synthetic/` con su propia configuración. Cualquier mezcla produce un error de calidad.

## `macetas.csv` — una fila por maceta

| Columna | Tipo / unidad | Obligatoria | Descripción |
| --- | --- | --- | --- |
| `pot_id` | texto | sí | Identificador único y estable (`M01` … `M06`) |
| `species` | texto | — | Especie (nombre científico si se conoce) |
| `substrate` | texto | — | Sustrato y procedencia |
| `location` | texto | — | Ubicación y exposición |
| `pair_id` | texto | — | Par de plantas similares (`P1` … `P3`) |
| `treatment` | `none`, `base`, `optimized` | — | Tratamiento asignado en la comparación física |
| `reference_mass_g` | g | sí, > 0 | `M_ref`: masa drenada de referencia (protocolo §4) |
| `reference_timestamp` | fecha con zona | sí | Cuándo se estableció `M_ref` |
| `pot_dimensions` | texto | — | Diámetro, altura, volumen aproximado |
| `plant_description` | texto | — | Tamaño de la planta y diferencias iniciales |
| `data_origin` | ver arriba | sí | |
| `notes` | texto | — | |

## `observaciones.csv` — una fila por lectura

| Columna | Tipo / unidad | Obligatoria | Descripción |
| --- | --- | --- | --- |
| `timestamp` | fecha con zona | sí | Hora real del pesaje |
| `pot_id` | texto | sí | Debe existir en `macetas.csv` |
| `observer` | texto | recomendada | Iniciales de quien midió |
| `phase` | `pilot`, `fit`, `validation`, `intervention` | sí | Debe coincidir con la ventana de `configs/data.json` |
| `treatment` | `none`, `base`, `optimized` | — | Política aplicada en ese momento |
| `reading_stage` | ver tabla siguiente | sí | |
| `mass_g` | g | sí (vacío si no se pudo pesar) | Masa de maceta + sustrato + planta |
| `irrigation_ml` | mL, ≥ 0 | solo en `post_drainage` | Agua aplicada en el evento |
| `drainage_ml` | mL, ≥ 0 | solo en `post_drainage` | Drenaje recogido durante el tiempo de drenaje |
| `irrigation_timestamp` | fecha con zona | solo en `post_drainage` | Hora real de aplicación del riego |
| `event_id` | texto | en etapas de riego | Vincula las filas de un mismo riego (`M01-E001`) |
| `ambient_temperature_c` | °C | — | Opcional; vacío si no se midió |
| `notes` | texto | — | Incidentes |
| `quality_flag` | `ok`, `suspect`, `bad` | sí | `bad` excluye la lectura del ajuste |
| `data_origin` | ver arriba | sí | |

### Etapas de lectura (`reading_stage`)

| Valor | Cuándo | Lleva `event_id` | Lleva riego/drenaje |
| --- | --- | --- | --- |
| `no_irrigation` | Revisión sin riego | no | no |
| `pre_irrigation` | Pesaje inmediatamente antes de regar | sí | no |
| `drainage_check` | Pesajes intermedios durante el drenaje (piloto) | sí | no |
| `post_drainage` | Pesaje al terminar el tiempo de drenaje | sí | **sí** |

**Ampliación respecto del plan:** se añadieron `irrigation_timestamp` (el plan pide registrar la hora de aplicación) y la etapa `drainage_check` (para estimar el tiempo de drenaje en el piloto), además de `data_origin`.

### Ejemplo ilustrativo (valores inventados, no son datos)

```csv
timestamp,pot_id,observer,phase,treatment,reading_stage,mass_g,irrigation_ml,drainage_ml,irrigation_timestamp,event_id,ambient_temperature_c,notes,quality_flag,data_origin
2026-11-12T07:04:00-06:00,M01,A,fit,base,pre_irrigation,912.4,,,,M01-E003,,,ok,observed
2026-11-12T07:37:00-06:00,M01,A,fit,base,post_drainage,1001.9,150,61,2026-11-12T07:06:00-06:00,M01-E003,,,ok,observed
2026-11-12T13:02:00-06:00,M01,B,fit,base,no_irrigation,988.0,,,,,,bandeja vacía,ok,observed
```

## `balanza.csv` — una fila por pesaje de verificación

| Columna | Tipo / unidad | Obligatoria | Descripción |
| --- | --- | --- | --- |
| `timestamp` | fecha con zona | sí | |
| `observer` | texto | — | |
| `scale_id` | texto | — | Identificador de la balanza |
| `object_id` | texto | sí | Objeto pesado repetidamente |
| `known_mass_g` | g | — | Masa conocida del objeto, si existe |
| `reading_g` | g | sí | Lectura |
| `resolution_g` | g, > 0 | sí | Resolución que muestra la balanza |
| `notes` | texto | — | |
| `data_origin` | ver arriba | sí | |

## Controles de calidad (`validate-data`)

**Errores** (impiden calibrar): columnas faltantes; fechas sin zona o inválidas; valores no numéricos; categorías no permitidas; `pot_id` desconocido o repetido; `M_ref` no positiva; lecturas duplicadas; riego o drenaje fuera de la fila `post_drainage`; valores negativos; `post_drainage` sin riego; etapas de riego sin `event_id`; eventos con más de una fila previa o posterior o con varias macetas; origen no permitido; `phase` distinta de su ventana.

**Advertencias** (se reportan y se conservan): masa faltante; drenaje u hora de riego no medidos; evento incompleto; hora de riego fuera del evento; drenaje mayor que el riego; masa por encima de `M_ref` más la tolerancia (déficit negativo); aumento de masa sin riego; lectura fuera de toda ventana; falta de verificación de balanza.

## Archivos derivados

| Archivo | Generado por | Contenido |
| --- | --- | --- |
| `data/processed/observaciones_procesadas.csv` | `calibrate` | Observaciones + `reference_mass_g`, `deficit_ml`, `split`, `usable` |
| `data/processed/intervalos_secado_fit.csv` | `calibrate` | Intervalos sin riego de la fase `fit` usados en el ajuste |
| `results/tables/calidad_datos.csv` | `validate-data`, `calibrate` | Incidencias de calidad |
| `results/tables/parametros.csv` | `calibrate` | Parámetros con unidad, tipo, método, incertidumbre, rango y origen |
| `results/tables/seleccion_modelos.csv` | `calibrate` | Comparación de modelos candidatos (AICc) |
| `results/tables/eventos_riego.csv` | `calibrate` | Contraste de cada riego con la regla de drenaje ideal |
| `results/tables/tiempo_drenaje.csv` | `calibrate` | Tiempo de estabilización tras el riego (piloto) |
| `results/tables/parametros_modelo.json` | `calibrate` | Parámetros para el simulador (B) |
| `results/tables/calibracion_manifest.json` | `calibrate` | Hash de los CSV, configuración, versiones, semillas y commit |
