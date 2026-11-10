**Contexto, datos y calibración**

**Problema y objetivo**

El riego con dosis y horario fijos puede aplicar más agua de la que una maceta perdió o dejar un déficit elevado antes de la siguiente revisión. Se estudia el peso de la maceta como indicador de cambios en el agua retenida y se establece una política fija como referencia para comparar decisiones de riego.

La pregunta de investigación es: ¿puede una política optimizada reducir el agua aplicada por maceta, respecto de un horario fijo razonable, manteniendo el déficit dentro de un intervalo operacional justificado?

Se construyó un modelo del balance de agua con separación entre ajuste de parámetros, simulación y verificación numérica. La calibración utiliza observaciones reservadas para ajuste y la validación compara predicciones con períodos posteriores. La métrica principal es el agua total aplicada, en mL por maceta durante un horizonte común, incluyendo la reposición final.

**Sistema y alcance**

El sistema comprende seis macetas de *Crassula ovata* (árbol de jade), con sustrato para cactus y suculentas, macetas plásticas idénticas y una ubicación protegida de lluvia. La especie se eligió por su crecimiento relativamente lento, que limita la deriva de masa, por su identificación inequívoca y por la existencia de guías de extensión sobre su riego (Mahr, 2025; UConn). La identificación de las plantas y las características del montaje se conservan en los metadatos. Las entradas son los riegos y las condiciones que determinan las pérdidas. El estado es el déficit respecto de la referencia drenada; las salidas son déficit, agua aplicada y drenaje.

Se excluyen automatización, crecimiento, rendimiento, salud de la planta y generalización a otras especies o estaciones. Un intervalo de déficit es una condición operacional y no una demostración de bienestar vegetal.

Como antecedentes se registran el trabajo de Lieth sobre riego de macetas con tensiómetros y el método gravimétrico de Kombala Liyanage et al. Sus condiciones no son equivalentes al montaje propuesto. Se emplean como contexto del método y de las métricas, sin adoptar sus porcentajes de ahorro ni sustituir las observaciones propias.

**Procedencia y organización de los datos**

Las observaciones propias se identifican mediante `data_origin = observed`. La procedencia, el momento de cada pesaje y las condiciones del montaje se conservan en los registros originales. Los datos sintéticos se identifican como `synthetic` y se emplean en pruebas de funcionamiento; los casos analíticos permiten verificar las reglas e integradores.

| Archivo | Contenido | Función |
| --- | --- | --- |
| `macetas.csv` | Identificación, especie, sustrato, ubicación y referencia drenada | Caracterización de cada maceta |
| `observaciones.csv` | Pesajes, riegos, drenaje, fechas y marcas de calidad | Calibración y comparación de predicciones |
| `balanza.csv` | Pesajes repetidos, resolución y comprobaciones instrumentales | Estimación del error de lectura |

**Protocolo y variable observada**

Se registra una masa drenada de referencia por maceta y se realizan pesajes en revisiones con hora real y zona horaria. Cuando hay riego se vinculan las lecturas previa y posterior mediante un identificador de evento. El riego y el drenaje se anotan una sola vez, después del drenaje. Los valores faltantes no se reemplazan por cero y los datos originales no se completan con estimaciones.

$$D(t)=\frac{M_{ref}-M(t)}{\rho_w},\qquad \rho_w\approx1\ \mathrm{g/mL}.$$

La interpretación supone que los otros componentes de la masa cambian poco durante el horizonte. El protocolo detallado se conserva en `docs/protocol.md` y las unidades y comprobaciones en `docs/data_dictionary.md`.

**Partición y calibración**

La separación se realiza mediante ventanas temporales completas de piloto, ajuste, validación e intervención, definidas en `configs/data.json`. Los períodos o ciclos de ajuste y validación se mantienen separados y la partición se congela antes del ajuste final. Las observaciones de validación quedan fuera de la selección de parámetros.

El código estima `a`, `b` y los factores horarios del modelo `dD/dt = q(t)max(0,a+bD)` usando intervalos de secado de la fase `fit`. Se comparan modelos de tasa constante, por bloques y por bloques con dependencia del déficit. Se selecciona el de menor complejidad entre los que quedan a menos de dos unidades del AICc mínimo. La incertidumbre se estima mediante remuestreo de días cuando existen suficientes días independientes.

Se comprobó la recuperación de parámetros conocidos con datos sintéticos y la conexión de su exportación con el simulador. La verificación incluye conservación del agua, casos analíticos, tratamiento de eventos y convergencia numérica.

**Validación con datos públicos reales**

Mientras se completan las observaciones propias, el modelo de pérdidas se contrastó con mediciones reales publicadas: los pesajes cada 15 min de 21 macetas de *Ensete ventricosum* en secado continuo (Chase, 2026; Zenodo, CC BY 4.0). Se identifican como `public` y se muestrearon a las mismas horas del protocolo. Los primeros 7 días se usaron para ajustar y los 7 siguientes para validar, sin recalibrar. Se excluyó una planta con aportes de agua no documentados, según una regla aplicada a todas.

El ajuste seleccionó la forma con dependencia del déficit (`a` = 21.6 mL/h, `b` = −0.0050 1/h, pérdida nocturna casi nula). En validación, el MAE agregado fue 172 mL (9.7 % del déficit medio). En las 16 macetas en que el ajuste por maceta identificó la reducción de pérdidas con el secado, el error mediano fue 3.7 % del déficit (60 mL). En las 5 en que el criterio AICc eligió una pérdida constante, el modelo sobrestimó el secado (error mediano 27.7 %), porque la validación se extiende a déficits mayores que los observados en el ajuste. Esto muestra el riesgo de extrapolar y la necesidad de que el ajuste propio cubra el rango de operación de las políticas. Los datos corresponden a otra especie y otra plataforma, por lo que comprueban la estructura del modelo y del procedimiento, no los parámetros del montaje de *Crassula ovata*.

**Control de medición y limitaciones**

El control de medición incluye repetibilidad de la balanza, referencias drenadas, horarios de pesaje y ciclos de secado. El intervalo operacional se sustenta en las características de la especie y en el piloto. Las fuentes recomiendan regar en profundidad cuando los ~2.5 cm superiores del sustrato están secos y evitar el agua estancada (Mahr, 2025; UConn). Ese criterio se registra en cada revisión mediante una prueba con palillo (`top_soil_dry`), y la calibración lo traduce a un déficit (`deficit_top_dry_median`). `D_seguro` se fija como el mayor déficit observado sin síntomas de estrés, de modo que las políticas no se evalúan fuera del rango registrado. La aproximación del drenaje mediante un evento instantáneo se evalúa con los residuos entre la respuesta observada y la predicha.

La frecuencia de pesaje limita la estimación del tiempo real fuera del intervalo. Varias lecturas de una maceta no equivalen a plantas independientes. El crecimiento, la caída de hojas y las diferencias entre plantas pueden alterar la relación entre masa y agua. La interpretación se limita al montaje y al período observados.

**Referencias**

Lieth, H. *Tensiometer-based irrigation of potted plants*. University of California, Davis. [Informe](https://lieth.ucdavis.edu/research/tens/96/potirg.htm).

Chase, R. R. (2026). *Transpiration monitoring reveals diverse drought coping strategies in wild and cultivated enset (Ensete ventricosum)* [Conjunto de datos]. Zenodo. [doi:10.5281/zenodo.23213759](https://doi.org/10.5281/zenodo.23213759).

Mahr, S. (2025). *Jade Plant, Crassula ovata*. Wisconsin Horticulture, University of Wisconsin–Madison. [Artículo](https://hort.extension.wisc.edu/articles/jade-plant-crassula-ovata/).

University of Connecticut, Home Garden Education Office. *Jade Plants (Crassula ovata)*. [Ficha](https://homegarden.cahnr.uconn.edu/factsheets/jade-plants).

Kombala Liyanage, D., Chathuranga, I., Mori, B. A. y Thilakarathna, M. S. (2022). *A Simple, Semi-Automated, Gravimetric Method to Simulate Drought Stress on Plants*. Agronomy, 12(2), 349. [Artículo](https://doi.org/10.3390/agronomy12020349).
