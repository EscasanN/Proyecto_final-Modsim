**Riego de macetas: simulación, optimización y validación**

Proyecto de CC3074 Modelización y Simulación, UVG 2026. Se representa el balance de agua de una maceta mediante Euler y RK4. La política fija define la referencia para comparar políticas de riego.

La formulación y la interfaz del simulador se describen en [docs/model.md](docs/model.md). Las contribuciones se registran en [docs/contributions.md](docs/contributions.md).

**Instalación en Windows**

Desde la raíz del repositorio se ejecuta:

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m pytest -q
```

En Linux o macOS se utiliza `.venv/bin/python`. Los comandos siguientes suponen que el entorno está activado; también se puede sustituir `python` por la ruta del intérprete del entorno.

La verificación se ejecutó con Python 3.13.2, NumPy 2.4.2, pandas 2.3.3, SciPy 1.17.0 y pytest 9.1.1. Las versiones se conservan en `requirements.txt`.

**Comprobación numérica y demostración**

```powershell
python -m src.macetas validate-model
python -m src.macetas simulate --parameters configs/demo_parameters.json --base configs/demo_base.json --allow-synthetic --out results/demo
```

El primer comando guarda casos conocidos y convergencia en `results/verification/`. El segundo ejecuta siete días con parámetros hipotéticos identificados como sintéticos y guarda trayectoria, riegos, métricas y un manifiesto con configuración y hashes. Estas salidas permiten verificar los integradores, los eventos y el balance de agua.

Para comparar integradores se puede repetir la simulación con `--method euler --step-h 0.5 --out results/demo_euler`. El método predeterminado es RK4 y el paso máximo configurado es 0.25 h. La comparación entre pasos permite evaluar la precisión numérica frente a la escala de las mediciones.

**Datos y calibración**

```powershell
python -m src.macetas validate-data
python -m src.macetas calibrate --config configs/model.json
```

La calibración utiliza exclusivamente intervalos de secado de la fase `fit`. Las ventanas temporales y los controles de calidad se definen en `configs/data.json`.

Para comprobar la conexión entre calibración y simulación se puede generar un conjunto sintético separado:

```powershell
python -m src.macetas make-synthetic --out data/synthetic
python -m src.macetas calibrate --config configs/model.json --data-config data/synthetic/data_config.json
python -m src.macetas simulate --parameters data/synthetic/salidas/tables/parametros_modelo.json --base configs/demo_base.json --allow-synthetic --out results/calibrated_demo
```

**Ejecución con mediciones**

La ejecución utiliza las observaciones originales, los metadatos del montaje, las referencias drenadas y la verificación de balanza. La partición se realiza por ventanas temporales completas y se congela antes del ajuste final. `configs/base.json` contiene el horizonte, el déficit inicial, la dosis, el horario, los límites y su justificación; el estado `frozen` identifica la configuración fijada para la comparación.

```powershell
python -m src.macetas calibrate --config configs/model.json
python -m src.macetas simulate --parameters results/tables/parametros_modelo.json --out results/base
```

Cuando la calibración selecciona parámetros por maceta se añade `--pot-id M01`, con el identificador correspondiente. El simulador exige una partición congelada y rechaza parámetros sintéticos salvo habilitación explícita. No se deben usar los valores de demostración como límites de manejo de una especie.

**Experimentos y validación (integrante D)**

Para la exposición, abre `iniciar_panel.cmd` con doble clic, o ejecuta:

```powershell
.venv\Scripts\python.exe -m src.macetas.presentation
```

Abre un panel local con maceta animada, reproducción de trayectorias, consola de
tareas, pruebas, comparación de políticas, errores de validación y figuras.
Funciona sin servicios externos una vez instaladas las dependencias.
Consulta la [guía de presentación](docs/presentation.md) para el recorrido sugerido.

```powershell
python -m pip install -r requirements-experiments.txt
python -m src.macetas.experiments --config configs/demo_experiments.json --allow-synthetic
python -m src.macetas.plots --experiments results/experiments/synthetic
```

La demostración evalúa B0/O0/B1/O1 con 30 semillas reservadas por condición, sin
volver a ejecutar PSO. Guarda tablas, trazabilidad y tres figuras PNG/PDF en
`results/experiments/synthetic/`. Es una demostración sintética, no validación real.
El procedimiento de validación con observaciones reservadas, comandos completos,
métricas y limitaciones se describen en [docs/validation.md](docs/validation.md).
La configuración real `configs/experiments.json` espera las entradas reales
congeladas de A/B/C; actualmente están pendientes.

**Archivos principales**

| Ruta | Contenido |
| --- | --- |
| `src/macetas/data_io.py`, `time_blocks.py`, `calibration.py` | Carga, calidad, bloques y estimación de pérdidas |
| `src/macetas/synthetic_data.py` | Datos sintéticos separados de las mediciones |
| `src/macetas/model.py` | Pérdida de agua, carga de parámetros y balance de riego |
| `src/macetas/integrators.py` | Euler y RK4 |
| `src/macetas/simulator.py` | Calendario de eventos, evolución, restricciones y cierre |
| `src/macetas/policies.py` | Interfaz de políticas y riego fijo |
| `src/macetas/simulation_io.py`, `verification.py` | Ejecución con archivos y comprobación analítica |
| `configs/` | Datos, calibración, simulación, política base y ejemplos sintéticos |
| `data/raw/` | CSV originales de mediciones |
| `results/verification/`, `results/demo/` | Salidas regenerables de verificación y demostración |
| `tests/` | Pruebas de datos, calibración, integradores y simulación |
| `docs/` | Protocolo, diccionario, formulación y contribuciones |
| `report/secciones/` | Texto de contexto y datos |


