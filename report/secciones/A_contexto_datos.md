**Contexto, datos y calibración**

**Problema y objetivo**

El riego con dosis y horario fijos puede aplicar más agua de la que una maceta perdió o dejar un déficit elevado antes de la siguiente revisión. Se propone estudiar el peso de la maceta como indicador de cambios en el agua retenida y comparar una política fija con una política optimizada.

La pregunta de investigación es: ¿puede una política optimizada reducir el agua aplicada por maceta, respecto de un horario fijo razonable, manteniendo el déficit dentro de un intervalo operacional justificado?

Se busca construir y verificar un modelo del balance de agua, estimar sus parámetros con observaciones reservadas para ajuste y comprobar sus predicciones con períodos posteriores. La métrica principal es el agua total aplicada, en mL por maceta durante un horizonte común, incluyendo la reposición final.

**Sistema y alcance**

Se considera un montaje de seis macetas comparables, una especie, un sustrato y una ubicación protegida de lluvia. La especie, el sustrato, el sitio y los instrumentos aún no están registrados. Las entradas son los riegos y las condiciones que determinan las pérdidas. El estado es el déficit respecto de la referencia drenada; las salidas son déficit, agua aplicada y drenaje.

Se excluyen automatización, crecimiento, rendimiento, salud de la planta y generalización a otras especies o estaciones. Un intervalo de déficit es una condición operacional y no una demostración de bienestar vegetal.

Como antecedentes se registran el trabajo de Lieth sobre riego de macetas con tensiómetros y el método gravimétrico de Kombala Liyanage et al. Sus condiciones no son equivalentes al montaje propuesto. Se emplean como contexto del método y de las métricas, sin adoptar sus porcentajes de ahorro ni sustituir las observaciones propias.

**Estado de los datos**

Al 2026-11-03, `macetas.csv`, `observaciones.csv` y `balanza.csv` contienen únicamente encabezados. No hay fechas de observación, especies identificadas, referencias drenadas, verificaciones instrumentales ni ciclos reales de secado y riego. Por ello no se presentan parámetros ajustados, errores de validación ni resultados de ahorro real.

| Conjunto | Macetas registradas | Lecturas registradas | Uso actual |
| --- | ---: | ---: | --- |
| Datos originales | 0 | 0 | Formatos preparados para mediciones |
| Datos sintéticos | Generables por código | Generables por código | Pruebas de funcionamiento |
| Casos analíticos | No aplica | No aplica | Verificación de reglas e integradores |

**Protocolo y variable observada**

Se registra una masa drenada de referencia por maceta y se realizan pesajes en revisiones con hora real y zona horaria. Cuando hay riego se vinculan las lecturas previa y posterior mediante un identificador de evento. El riego y el drenaje se anotan una sola vez, después del drenaje. Los valores faltantes no se reemplazan por cero y los datos originales no se completan con estimaciones.

$$D(t)=\frac{M_{ref}-M(t)}{\rho_w},\qquad \rho_w\approx1\ \mathrm{g/mL}.$$

La interpretación supone que los otros componentes de la masa cambian poco durante el horizonte. El protocolo detallado se conserva en `docs/protocol.md` y las unidades y comprobaciones en `docs/data_dictionary.md`.

**Partición y calibración**

La separación se define mediante ventanas temporales completas de piloto, ajuste, validación e intervención. Las ventanas de `configs/data.json` todavía no tienen fechas y no están congeladas. Antes del ajuste final se deben fijar períodos o ciclos completos, conservando los de validación fuera de la selección de parámetros.

El código estima `a`, `b` y los factores horarios del modelo `dD/dt = q(t)max(0,a+bD)` usando intervalos de secado de la fase `fit`. Se comparan modelos de tasa constante, por bloques y por bloques con dependencia del déficit. Se selecciona el de menor complejidad entre los que quedan a menos de dos unidades del AICc mínimo. La incertidumbre se estima mediante remuestreo de días cuando existen suficientes días independientes.

Se comprobó la recuperación de parámetros conocidos con datos sintéticos y la conexión de su exportación con el simulador. Este resultado verifica la implementación; la validez física sigue pendiente de las mediciones.

**Limitaciones y pendientes**

Se requiere comprobar la repetibilidad de la balanza, establecer referencias drenadas, elegir horarios, justificar el límite operacional con información de la especie y registrar varios ciclos de secado. También falta cuantificar si el drenaje puede aproximarse mediante un evento instantáneo.

La frecuencia de pesaje limita la estimación del tiempo real fuera del intervalo. Varias lecturas de una maceta no equivalen a plantas independientes. El crecimiento, la caída de hojas y las diferencias entre plantas pueden alterar la relación entre masa y agua. Las conclusiones finales deberán limitarse al montaje y al período observados.

**Referencias**

Lieth, H. *Tensiometer-based irrigation of potted plants*. University of California, Davis. [Informe](https://lieth.ucdavis.edu/research/tens/96/potirg.htm).

Kombala Liyanage, D., Chathuranga, I., Mori, B. A. y Thilakarathna, M. S. (2022). *A Simple, Semi-Automated, Gravimetric Method to Simulate Drought Stress on Plants*. Agronomy, 12(2), 349. [Artículo](https://doi.org/10.3390/agronomy12020349).
