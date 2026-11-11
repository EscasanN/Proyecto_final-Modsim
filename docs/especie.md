**Especie del ensayo: *Crassula ovata* (árbol de jade)**

> **Trabajo futuro.** Este documento describe el montaje propio de *Crassula ovata* que no se llegó a medir. El sistema real de la entrega es el ensayo de Chase (2026); ver `docs/sistema_enset.md`.

Responsable: Nelson Escalante.

**Selección**

Se emplea *Crassula ovata* (Mill.) Druce, conocida como árbol de jade o planta del dinero. Es una suculenta de tallos y hojas carnosas, cultivada con frecuencia en maceta. Su elección responde a cuatro criterios del montaje:

| Criterio | Fundamento |
| --- | --- |
| Poca deriva de masa | Crecimiento relativamente lento [Mahr 2025]; durante algunas semanas la variación de masa se atribuye principalmente al agua |
| Identificación clara | Se reconoce sin ambigüedad, a diferencia de los híbridos de *Echeveria*, cuya especie suele no estar identificada en venta |
| Fuentes de manejo | Existen guías de extensión universitaria sobre su riego [Mahr 2025; UConn] |
| Tolerancia | Tolera amplios rangos de temperatura y periodos de secado entre riegos [Mahr 2025], lo que reduce el riesgo de pérdida de plantas durante el ensayo |

**Manejo hídrico según las fuentes**

- Se recomienda dejar secar el sustrato entre riegos profundos [Mahr 2025].
- Se riega cuando los ~2.5 cm (una pulgada) superiores del sustrato están secos; algunos productores remojan la planta aproximadamente una vez por semana y la dejan drenar por completo [UConn].
- Durante los meses de días cortos y frescos (mediados de octubre a mediados de marzo en la referencia) se reduce la cantidad y la frecuencia del riego, sin dejar secar el sustrato por completo [UConn].
- El exceso de riego provoca caída de hojas, pudrición del tallo y edema; la sequía provoca enanismo, manchas, caída de hojas y arrugamiento [Mahr 2025; UConn].
- Requiere sustrato de drenaje rápido para cactus y suculentas y no debe quedar agua en el plato [Mahr 2025; UConn].
- Se cultiva con cuatro o más horas de sol directo; con poca luz el crecimiento es débil [Mahr 2025].

Las fuentes corresponden a cultivo en interiores en Estados Unidos. Su calendario estacional no se traslada directamente a Guatemala; se utilizan como criterio cualitativo, y los valores numéricos del ensayo se obtienen del piloto.

**Implicaciones para el montaje**

| Elemento | Decisión | Motivo |
| --- | --- | --- |
| Plantas | Seis ejemplares de tamaño y número de tallos similares, agrupados en tres pares | Comparabilidad entre tratamientos |
| Recipiente | Maceta plástica idéntica, de 10 a 12 cm, con orificios de drenaje | UConn sugiere barro; se usa plástico porque la pared de barro absorbe y evapora agua, lo que altera la masa y el balance. Se declara como desviación |
| Sustrato | Mezcla comercial para cactus y suculentas, de un mismo lote | Drenaje rápido [Mahr 2025; UConn] |
| Ubicación | Cuatro o más horas de sol directo o luz brillante, protegida de lluvia y con exposición comparable | [Mahr 2025] |
| Riego | Aplicación al sustrato hasta obtener drenaje, sin mojar hojas; bandeja vaciada después del drenaje | Riego profundo y sin agua estancada [Mahr 2025; UConn] |
| Balanza | Capacidad superior a la masa total de la maceta; resolución de 0.1 g preferible | La pérdida diaria de una suculenta es pequeña; con 1 g de resolución debe cumplirse el criterio de cinco `sigma_lectura` entre revisiones |

**Prueba del sustrato superficial**

Después de cada pesaje `pre_irrigation` o `no_irrigation` se introduce un palillo de madera limpio a 2.5 cm de profundidad, junto al borde de la maceta, y se retira tras unos segundos. Se registra `top_soil_dry = yes` si sale seco y sin sustrato adherido y `no` en caso contrario. La prueba se hace después del pesaje para no alterar la masa leída y siempre con el mismo procedimiento.

`calibrate` calcula, para cada ciclo de secado de piloto y ajuste, el déficit en la primera lectura con `top_soil_dry = yes` (`results/tables/umbral_sustrato_seco.csv`, parámetro `deficit_top_dry_median`). Así el criterio de riego de las fuentes se expresa en la variable del modelo.

**Intervalo operacional propuesto**

| Magnitud | Definición | Momento de fijación |
| --- | --- | --- |
| `D_riego` | Mediana de `deficit_top_dry` entre ciclos de piloto y ajuste: déficit al que las fuentes indican regar | Al congelar la partición |
| `D_seguro` | Mayor déficit alcanzado en piloto y ajuste sin síntomas de estrés (arrugamiento o caída de hojas), y no menor que `D_riego` | Antes de optimizar |

`D_seguro` queda dentro del rango observado, de modo que ninguna política se evalúa en condiciones más secas que las registradas. Es común a la política base y a la optimizada. No se presenta como garantía fisiológica sino como límite operacional del ensayo.

**Recomendaciones para la política base**

La práctica descrita por UConn, un remojo aproximadamente semanal con drenaje completo, ofrece una referencia fija y razonable: dosis constante a las 07:00 cada `n` días. Los valores de dosis y periodo se fijan con el piloto, por ejemplo la dosis media que produjo drenaje y el periodo observado hasta `top_soil_dry = yes`. La configuración corresponde a `configs/base.json`.

**Duración de la observación**

Los ciclos de secado de una suculenta duran varios días. La ventana `fit` termina cuando cada maceta completa al menos dos ciclos de secado y riego, y la ventana `validation` incluye al menos un ciclo completo adicional. Se estiman de dos a tres semanas después del piloto; la duración final se registra al congelar la partición.

**Síntomas que se registran en `notes`**

Hojas arrugadas o blandas, caída de hojas, manchas o ampollas, tallo blando u oscuro, plagas (cochinilla algodonosa) y flores. La caída de hojas también se registra porque modifica la masa sin relación con el agua.

**Referencias**

Mahr, S. (2025). *Jade Plant, Crassula ovata*. Wisconsin Horticulture, Division of Extension, University of Wisconsin–Madison. [Artículo](https://hort.extension.wisc.edu/articles/jade-plant-crassula-ovata/).

University of Connecticut, Home Garden Education Office. *Jade Plants*. [Ficha](https://homegarden.cahnr.uconn.edu/factsheets/jade-plants).
