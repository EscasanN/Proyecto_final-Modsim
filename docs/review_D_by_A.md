**Revisión técnica cruzada: área D (Diego Ramirez), revisada por A (Nelson Escalante)**

Fecha: 2026-11-10 · Commit revisado: `93b15fb` · Alcance: `experiments.py`, `metrics.py`, `validation.py`, `plots.py`, `presentation.py` y `presentation_assets/`, pruebas asociadas, `docs/validation.md` y resultados en `results/experiments/synthetic/` y `results/validation/synthetic/`.

**Procedimiento**

1. Lectura del código y de la documentación de D.
2. Suite completa con `python -m pytest`: 130 pruebas aprobadas.
3. Reejecución de `python -m src.macetas.experiments --config configs/demo_experiments.json --allow-synthetic` en una carpeta aparte y comparación con `results/experiments/synthetic/runs.csv`. Las tablas son idénticas, salvo `duration_s` (tiempo de pared); la diferencia numérica máxima es 0.
4. Ejecución de la validación temporal con datos públicos reales (Chase, 2026) y con datos sintéticos.
5. Prueba del panel en un navegador: carga, reproducción de trayectorias, «Simular maceta», «Validar predicciones» y «Ejecutar todas las pruebas».

**Aspectos correctos**

- Diseño pareado B0/O0/B1/O1: ambas políticas reciben las mismas realizaciones ambientales y de error de lectura por semilla. La sensibilidad escala el mismo ambiente en 20 %.
- Separación de semillas: se usan solo las 30 de evaluación reservadas por C, sin volver a optimizar. Se verifica por hash que parámetros, base, modelo y configuración no cambiaron desde la selección de la política.
- La factibilidad la decide el auditor de C. `optimized_better` exige que ambas políticas sean factibles. Los resultados desfavorables (O1 0/30) se reportan sin ocultarlos.
- Métricas con unidades, desviación muestral, diferencias pareadas y residuo de conservación por ejecución (`balance.csv`).
- Validación temporal sin recalibración ni reinicio, con la partición y los hashes comprobados contra el manifiesto de calibración, e inicialización excluida de los errores.
- Panel restringido a `127.0.0.1`, con token y comprobación de origen en las solicitudes, solo comandos fijos del proyecto y protección contra rutas fuera de `results/`.

**Hallazgos**

| # | Severidad | Archivo | Hallazgo | Estado |
| --- | --- | --- | --- | --- |
| 1 | Media | `validation.py` | Siempre pasa `pot_id` a `load_calibrated_model`, que en ese caso devuelve los parámetros por maceta sin consultar `selected_scope`. Una calibración agrupada (`pooled`) se valida en silencio con parámetros por maceta. Propuesta: `pot = pot_id if payload["selected_scope"] == "per_pot" else None`, coordinada con B, porque el comportamiento nace en `model.py` | Pendiente (D y B) |
| 2 | Media | `plots.py` | La figura 1 tomaba el origen de los experimentos aunque mostrara observaciones de validación; con datos públicos decía «Origen: synthetic». Además solo mostraba la primera maceta | Corregido por A en `021eb21` (origen desde la validación y figura `04_validation_all`) |
| 3 | Baja | `experiments.py` | `stochastic = daily_cv > 0 or sigma > 0` lanza `TypeError` si `sigma_deficit_ml` es nulo (calibración sin verificación de balanza, como en los datos públicos). Se sugiere un error explícito que pida la verificación de balanza | Pendiente (D) |
| 4 | Baja | `presentation.py`, `iniciar_panel.cmd` | «Ejecutar todas las pruebas» usa `--basetemp=.venv/...`; sin carpeta `.venv` falla con 49 errores `FileNotFoundError`, aunque las pruebas pasan con `python -m pytest`. `iniciar_panel.cmd` también exige `.venv`. Se sugiere un `basetemp` en `results/presentation/` y que el `.cmd` use `python` si no hay entorno virtual | Pendiente (D) |
| 5 | Baja | `presentation_assets/app.js`, `presentation.py` | Textos fijos: la validación siempre se rotula «Validación sintética» y el estado real siempre dice «Pendiente», aunque ya existe la validación con datos públicos (`results/validation/public_enset/`) y la tabla de la Parte 6 (`results/tables/comparacion_real.md`). Se sugiere leer el origen desde `validation_manifest.json` y mostrar ambas evidencias | Pendiente (D) |
| 6 | Baja | `plots.py` | Con `--validation`, las figuras 02 y 03 de la carpeta de validación repiten los experimentos sintéticos. Está documentado en el README, pero conviene no generarlas en esa carpeta | Corregido por A el 2026-11-11 (`--validation-only`) |
| 7 | Documentación | `docs/`, `report/` | Falta `docs/presentation.md`, citado en `results/presentation/README.md`. Falta la sección de D en `report/secciones/` y sus aportes en `docs/contributions.md` | Pendiente (D) |
| 8 | Baja | `tests/test_presentation.py` | `test_http_execution_and_origin_guard` falla de forma intermitente (1 de 3 ejecuciones el 2026-11-11) con un error de conexión al servidor HTTP local; el resto de la suite pasa. Probablemente es una condición de carrera al iniciar el servidor en la prueba | Pendiente (D) |

**Observación para el informe**

`paired_summary.csv` promedia ahorros de pares factibles e inviables. Para la condición normal, el ahorro medio es 26.75 % en los 30 pares y 26.8 % en los 26 pares en que ambas políticas cumplen las restricciones. Con pérdidas +20 % no hay ningún par factible, por lo que el ahorro de 19.1 % no debe presentarse como mejora. Se recomienda reportar en el informe el ahorro de los pares factibles junto con la proporción de factibilidad.

**Conclusión**

El trabajo de D cumple los requisitos de diseño experimental, repeticiones, control de aleatoriedad y validación de la rúbrica. Es reproducible y no se encontraron errores en los resultados numéricos. Los hallazgos 1 y 3 afectan la robustez con datos reales y conviene resolverlos antes de la evaluación con mediciones propias. Los hallazgos 4 a 7 afectan la demostración y la documentación.
