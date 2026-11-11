# Experimentos y validación (integrante D)

> **Actualización (2026-11-11).** Ya existen resultados con mediciones reales públicas del sistema adoptado (Chase, 2026): validación en `results/validation/public_enset/`, optimización y experimentos en `results/optimization/public_enset/` y `results/experiments/public_enset/`. Ver `docs/sistema_enset.md`.

## Alcance y estado

Se reutilizan la carga y calibración de A, el motor de B y la política,
generador ambiental y auditor independiente de C. Sus módulos no se modifican.
Los CSV reales en `data/raw/` son plantillas: la validación real, los límites
justificados, la base real y la política optimizada real siguen pendientes.
La demostración usa exclusivamente parámetros y políticas sintéticos existentes.
No constituye evidencia agronómica ni validación contra la realidad.

## Diseño experimental

`experiments.py` evalúa B0 y O0 con pérdidas normales y B1/O1 con las mismas
realizaciones multiplicadas por 1.20. La política O es la misma política
congelada por C, sin nueva búsqueda ni selección durante evaluación.
Cada ejecución crea una instancia nueva de política para limpiar su presupuesto diario.
Se conservan horizonte, estado inicial, integrador, paso, revisiones y restricciones
de la política congelada. Las discrepancias se rechazan.

Las configuraciones `experiments.json` y `demo_experiments.json` referencian las
configuraciones de C sin duplicar límites, horizonte o bancos de semillas.
Los bancos search, selection, evaluation y optimizer se verifican únicos y disjuntos.
Se usan las 30 semillas evaluation reservadas por C; nunca se ejecuta PSO.
El generador de C usa subflujos independientes para ambiente y error de lectura;
ambas políticas reciben exactamente las mismas realizaciones por semilla.
El mismo ambiente normal también sirve para la sensibilidad, escalado en 20 %.
Si ambiente y medición son deterministas, se ejecuta una sola realización por
condición y no se presentan copias como réplicas independientes.
El CV 0.10 de la demostración es hipotético, según `demo_pso.json`.

## Métricas y salidas

`runs.csv` registra agua total y reposición final [mL], drenaje [mL], déficit
máximo [mL], tiempo sobre límite [h], eventos operacionales y de cierre [conteos],
tiempo de ejecución [s], origen, semilla y factibilidad del auditor de C.
La reposición final se incluye en el consumo y en los presupuestos de C.
`balance.csv` conserva el residuo D_final - D_inicial - pérdidas + riego - drenaje [mL].
`summary.csv` contiene media, desviación estándar muestral (ddof=1) y proporción
factible por condición; la desviación es ausente cuando hay una sola ejecución.
`paired.csv` contiene diferencias O-B por métrica y ahorro B-O [mL]; ahorro
porcentual = 100(B-O)/B únicamente para B positivo. Un valor de ahorro puede
existir en una ejecución inviable: `optimized_better` exige ambas políticas
factibles y ahorro positivo. No se declara superioridad global a partir de
una media que mezcla ejecuciones factibles e inviables.
`paired_summary.csv` resume media y desviación de los ahorros pareados, junto
con la proporción de pares en que ambas políticas cumplen las restricciones.

`trajectory.csv` y `events.csv` permiten regenerar figuras sin simular.
`evaluation_scenarios.json` registra todos los factores ambientales y errores.
`manifest.json` registra configuraciones, parámetros, política completa, versiones,
semillas y SHA256 de entradas y fuentes. Los resultados numéricos son reproducibles;
los tiempos de pared varían. No se promete identidad binaria de imágenes o PDF.
Las entradas se contrastan con los hashes del manifiesto de optimización de C
para impedir evaluar una política seleccionada con parámetros luego modificados.

## Validación temporal

`validation.py` utiliza `load_dataset` de A, exige ausencia de errores de calidad,
partición congelada, ventanas de validación posteriores a todas las de ajuste,
origen, densidad y referencias compatibles con la calibración.
Requiere `calibracion_manifest.json` junto a los parámetros; comprueba que la
partición y los hashes de los datos coincidan con la calibración de A. Esto
impide cambiar silenciosamente datos o ventanas después del ajuste. Los parámetros
deben proceder del comando de calibración de A, que ajusta exclusivamente `fit`.
No se ajustan parámetros en el módulo de validación.

Por maceta y ventana se inicializa una sola vez desde la primera lectura utilizable,
excluida de las métricas; se predice hasta la última lectura con los riegos
realmente registrados. Se rechazan eventos incompletos. No se reinicia la trayectoria
con lecturas posteriores. Lecturas previas al riego se comparan antes del salto;
las posteriores usan la evolución después del riego. Se insertan los instantes
observados como fronteras del integrador, sin interpolación entre eventos.
Se excluyen `drainage_check`, lecturas no utilizables y la inicialización.
No se imputan observaciones ni cantidades de riego ausentes.

MAE = media(|predicción-observación|), RMSE = raíz de la media de errores cuadrados,
sesgo = media(predicción-observación), todos en mL. `errors.csv` reporta cada maceta
y ALL, agregado por observaciones (no media de medias). `comparisons.csv` conserva
fecha, fila de origen, ventana y errores. El manifiesto registra origen, partición,
inicialización y hashes; `real_validation` es falso para conjuntos sintéticos.

El motor representa drenaje instantáneo. El drenaje retardado y el error instrumental
pueden afectar las lecturas posteriores al riego. Una nueva ventana tiene una nueva
condición inicial declarada; no es una predicción continua a través de huecos.
Esta validación de dinámica es distinta de evaluar políticas contrafactuales.
No se infiere bienestar fisiológico a partir del déficit de masa.

## Ejecución

Desde la raíz, con el entorno activado:

```powershell
python -m pip install -r requirements-experiments.txt
python -m src.macetas.experiments --config configs/demo_experiments.json --allow-synthetic
python -m src.macetas.plots --experiments results/experiments/synthetic
python -m src.macetas make-synthetic --out data/synthetic
python -m src.macetas calibrate --config configs/model.json --data-config data/synthetic/data_config.json
python -m src.macetas.validation --data-config data/synthetic/data_config.json --parameters data/synthetic/salidas/tables/parametros_modelo.json --allow-synthetic --out results/validation/synthetic
python -m src.macetas.plots --experiments results/experiments/synthetic --validation results/validation/synthetic --out results/validation/synthetic/figures
python -m pytest -q --assert=plain --basetemp=.venv/test-final
```

Las figuras PNG/PDF muestran dinámica, agua operacional y reposición, dispersión
del drenaje y sensibilidad/factibilidad. Sin datos de validación se rotula
explícitamente que no hay observaciones. Con `--validation`, la primera figura
compara las observaciones reservadas y predicciones de la primera maceta/ventana;
las tablas conservan todas las macetas. No se aplica un límite de política a
la validación si no existe un límite real documentado.

Para datos reales, tras completar y congelar las entradas de A/B/C:

```powershell
python -m src.macetas.experiments --config configs/experiments.json
python -m src.macetas.validation --data-config configs/data.json --parameters results/tables/parametros_modelo.json --out results/validation/observed
python -m src.macetas.plots --experiments results/experiments/observed --validation results/validation/observed
```

Actualmente el primer comando rechaza el estado pendiente. No se genera la tabla
referencia real/base/mejora exigida por el enunciado con cifras inventadas: requiere
mediciones comparables y una base y política reales congeladas. La incertidumbre
simulada proviene del generador especificado; 30 simulaciones no equivalen a 30 plantas.
