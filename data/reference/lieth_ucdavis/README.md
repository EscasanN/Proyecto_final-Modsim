**Caso documentado: riego por tensiómetro en macetas (Lieth, UC Davis)**

| Campo | Valor |
| --- | --- |
| Fuente | Lieth, H. *Tensiometer-based irrigation of potted plants*. Environmental Horticulture, University of California, Davis |
| URL | https://lieth.ucdavis.edu/research/tens/96/potirg.htm |
| Fecha de consulta | 2026-11-03 |
| Periodo | Experimentos de 1989 a 1990 en invernaderos comerciales de California |
| Contenido | Agua aplicada por maceta (mL/día) con el riego del productor y con riego activado por tensiómetro, y ahorro reportado |

`agua_aplicada.csv` transcribe la tabla publicada (`data_origin = public`). En los experimentos 3 y 5 la fuente indica que el valor del productor es una cota inferior, porque se desbordaron los recipientes de recolección (`grower_is_lower_bound = true`); esos dos experimentos se excluyen de los resúmenes numéricos.

Es un caso de referencia documentado, no una serie temporal: no permite calibrar el modelo. Se usa para contrastar la métrica principal (agua aplicada por maceta) y la magnitud de la mejora de un riego guiado por mediciones frente a un riego fijo. Especies, macetas, clima y sistema de control difieren del montaje del proyecto.
