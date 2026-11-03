**Riego de macetas: simulación, optimización y validación**

Proyecto de CC3074 Modelización y Simulación, UVG 2026. Se representa el balance de agua de una maceta mediante Euler y RK4. La política fija sirve como referencia para integrar después una política optimizada con enjambre de partículas.

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

El primer comando guarda casos conocidos y convergencia en `results/verification/`. El segundo ejecuta siete días con parámetros hipotéticos identificados como sintéticos y guarda trayectoria, riegos, métricas y un manifiesto con configuración y hashes. Estas salidas comprueban el programa y no validan el comportamiento de plantas reales.

Para comparar integradores se puede repetir la simulación con `--method euler --step-h 0.5 --out results/demo_euler`. El método predeterminado es RK4 y el paso máximo es 0.25 h; su elección definitiva depende de los datos y de la precisión de la balanza.

**Datos y calibración**

```powershell
python -m src.macetas validate-data
python -m src.macetas calibrate --config configs/model.json
```

La calibración requiere mediciones utilizables y una ventana `fit` definida en `configs/data.json`. Sin ellas se detiene con un mensaje explicativo. Que los CSV vacíos superen el control de formato no significa que existan datos suficientes.

Para comprobar la conexión entre calibración y simulación se puede generar un conjunto sintético separado:

```powershell
python -m src.macetas make-synthetic --out data/synthetic
python -m src.macetas calibrate --config configs/model.json --data-config data/synthetic/data_config.json
python -m src.macetas simulate --parameters data/synthetic/salidas/tables/parametros_modelo.json --base configs/demo_base.json --allow-synthetic --out results/calibrated_demo
```

**Ejecución con mediciones reales**

Se completan las mediciones originales, la especie, el sustrato, las referencias drenadas y la verificación de balanza. Se definen y congelan ventanas temporales completas antes del ajuste final. Se completa `configs/base.json` con horizonte, déficit inicial, dosis, horario, límites y justificación; su estado pasa a `frozen` cuando esas decisiones están sustentadas.

```powershell
python -m src.macetas calibrate --config configs/model.json
python -m src.macetas simulate --parameters results/tables/parametros_modelo.json --out results/base
```

Cuando la calibración selecciona parámetros por maceta se añade `--pot-id M01`, con el identificador correspondiente. El simulador exige una partición congelada y rechaza parámetros sintéticos salvo habilitación explícita. No se deben usar los valores de demostración como límites de manejo de una especie.

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
| `configs/` | Datos, calibración, simulación, política real pendiente y ejemplos sintéticos |
| `data/raw/` | CSV originales de mediciones |
| `results/verification/`, `results/demo/` | Salidas regenerables de verificación y demostración |
| `tests/` | Pruebas de datos, calibración, integradores y simulación |
| `docs/` | Protocolo, diccionario, formulación y contribuciones |
| `report/secciones/` | Texto de contexto y datos |

**Uso de IA**

Se utilizó IA para investigación adicional del tema, explicación de conceptos, apoyo logístico del plan de trabajo y asistencia en programación y pruebas. No se generaron mediciones mediante IA.
