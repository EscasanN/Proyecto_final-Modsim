**Riego de macetas: simulación, optimización y validación**

Proyecto de CC3074 Modelización y Simulación, UVG 2026. El balance de agua de una maceta se representa con una ecuación diferencial resuelta con Euler y RK4. Una política de riego por umbrales se optimiza con enjambre de partículas (PSO) y se compara con una política fija.

**Sistema real.** El sistema estudiado es el ensayo documentado de Chase (2026, Zenodo, [doi:10.5281/zenodo.23213759](https://doi.org/10.5281/zenodo.23213759), CC BY 4.0): macetas de *Ensete ventricosum* pesadas cada 15 min en una plataforma gravimétrica. Son mediciones públicas de terceros (`data_origin = public`); el equipo no las midió. Las mediciones propias previstas con *Crassula ovata* no se realizaron y quedan como trabajo futuro. El cambio de alcance y el origen de cada entrada se explican en [docs/sistema_enset.md](docs/sistema_enset.md).

**Instalación**

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt -r requirements-experiments.txt
.venv\Scripts\python.exe -m pytest -q
```

En Linux o macOS se usa `.venv/bin/python`. También funciona con un Python global que tenga las dependencias instaladas. Los comandos se ejecutan desde la raíz del repositorio.

**Flujo principal (sistema real)**

```powershell
python -m src.macetas import-public                                   # descarga previa: data/reference/chase2026_enset/README.md
python -m src.macetas validate-data --config data/reference/chase2026_enset/converted/data_config.json
python -m src.macetas calibrate --config configs/model_public_enset.json
python -m src.macetas.validation --data-config data/reference/chase2026_enset/converted/data_config.json --parameters data/reference/chase2026_enset/converted/salidas/tables/parametros_modelo.json --out results/validation/public_enset
python -m src.macetas.plots --validation results/validation/public_enset --validation-only
python -m src.macetas optimize --config configs/pso_enset.json
python -m src.macetas.experiments --config configs/experiments_enset.json
python -m src.macetas.plots --experiments results/experiments/public_enset
python -m src.macetas.comparison_table
```

| Etapa | Resultados | Descripción |
| --- | --- | --- |
| Datos públicos | `data/reference/chase2026_enset/` | Fuente, licencia, conversión y exclusiones |
| Calibración | `results/calibration/public_enset/` | Parámetros por maceta en la ventana de ajuste |
| Validación | `results/validation/public_enset/` | Predicción de la ventana reservada, sin recalibrar |
| Optimización | `results/optimization/public_enset/` | PSO y búsqueda aleatoria; política congelada |
| Experimentos | `results/experiments/public_enset/` | B0/O0/B1/O1 con 30 semillas reservadas |
| Parte 6 | `results/tables/comparacion_real_enset.md` | Referencia real, simulación base y simulación mejorada |

La calibración se copia de `data/reference/chase2026_enset/converted/salidas/tables/` a `results/calibration/public_enset/`, ruta que usan la optimización y los experimentos.

**Comprobación numérica y demostración sintética**

```powershell
python -m src.macetas validate-model
python -m src.macetas simulate --parameters configs/demo_parameters.json --base configs/demo_base.json --allow-synthetic --out results/demo
python -m src.macetas.experiments --config configs/demo_experiments.json --allow-synthetic
```

`validate-model` guarda casos analíticos y convergencia en `results/verification/`. Las demás demostraciones usan parámetros sintéticos identificados como tales (`results/synthetic_calibration/`, `results/optimization/synthetic/`, `results/experiments/synthetic/`, `results/validation/synthetic/`). Sirven para comprobar integradores, eventos y balance; no son validación real.

**Panel de presentación**

```powershell
python -m src.macetas.presentation
```

Abre un panel local en `http://127.0.0.1:8765` con trayectorias animadas, consola de tareas, comparación de políticas, errores de validación y figuras. `iniciar_panel.cmd` lo inicia con doble clic si existe `.venv`. Las salidas del panel se guardan en `results/presentation/`, que no se versiona.

**Archivos principales**

| Ruta | Contenido |
| --- | --- |
| `src/macetas/data_io.py`, `time_blocks.py`, `calibration.py` | Carga, calidad, bloques horarios y estimación de pérdidas |
| `src/macetas/public_data.py` | Conversión de los datos públicos de Chase (2026) |
| `src/macetas/synthetic_data.py` | Datos sintéticos de prueba |
| `src/macetas/model.py`, `integrators.py`, `simulator.py`, `policies.py` | Balance de agua, Euler/RK4, eventos y políticas |
| `src/macetas/simulation_io.py`, `verification.py` | Ejecución con archivos y comprobación analítica |
| `src/macetas/pso.py`, `optimization.py`, `constraints.py` | PSO, búsqueda y auditoría independiente de restricciones |
| `src/macetas/experiments.py`, `metrics.py`, `validation.py`, `plots.py` | Evaluación final, métricas, validación temporal y figuras |
| `src/macetas/comparison_table.py` | Tabla de la Parte 6 |
| `src/macetas/presentation.py`, `presentation_assets/` | Panel local |
| `configs/*_enset.json` | Configuraciones del sistema real |
| `configs/demo_*.json` | Demostración sintética |
| `configs/data.json`, `base.json`, `pso.json`, `experiments.json` | Plantillas para mediciones propias (trabajo futuro) |
| `data/raw/` | Plantillas vacías para mediciones propias (trabajo futuro) |
| `docs/` | Sistema real, modelo, validación, calibración, datos, protocolo futuro, revisiones, referencias y contribuciones |
| `report/secciones/` | Borradores de secciones del informe |

Formulación del modelo: [docs/model.md](docs/model.md). Validación y experimentos: [docs/validation.md](docs/validation.md). Contribuciones: [docs/contributions.md](docs/contributions.md).

**Uso de IA**

Se utilizó IA para investigación adicional del tema, explicación de conceptos, apoyo logístico del plan de trabajo y asistencia en programación y pruebas. No se generaron mediciones mediante IA; los datos proceden de Chase (2026) y Lieth (UC Davis), citados en `docs/references.bib`.
