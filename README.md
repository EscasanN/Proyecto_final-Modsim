# Riego de macetas: simulación, optimización y validación

Proyecto 2 de CC3074 Modelización y Simulación (UVG, 2026). Simula el balance de agua en macetas (Euler/RK4) y optimiza una política de riego con enjambre de partículas (PSO). El modelo se valida contra mediciones propias.

> README en construcción: D integra la versión final. Cada integrante documenta aquí los comandos de su módulo.

## Instalación

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate    ·    Linux/macOS: source .venv/bin/activate
python -m pip install -r requirements.txt
python -m pytest
```

Verificado con Python 3.14.3. Ejecuta los comandos desde la raíz del repositorio.

## Datos y calibración (Nelson Escalante)

```bash
python -m src.macetas validate-data                               # controles de calidad de data/raw
python -m src.macetas calibrate --config configs/model.json       # ajuste de pérdidas con la fase fit
```

Para desarrollar sin mediciones reales, hay un conjunto **sintético** etiquetado:

```bash
python -m src.macetas make-synthetic --out data/synthetic
python -m src.macetas calibrate --config configs/model.json --data-config data/synthetic/data_config.json
```

Documentación: [protocolo](docs/protocol.md) · [diccionario de datos](docs/data_dictionary.md) · [calibración](docs/calibration.md).

## Estructura

| Ruta | Contenido |
| --- | --- |
| `configs/` | `data.json` (datos y partición), `model.json` (bloques horarios, calibración y, después, el simulador) |
| `data/raw/` | Mediciones originales; solo se agregan filas |
| `data/processed/` | Datos derivados por `calibrate` |
| `src/macetas/` | Código: `data_io`, `time_blocks`, `calibration`, `synthetic_data` (Nelson Escalante); modelo, integradores, PSO y experimentos (B, C y D) |
| `tests/` | Pruebas automatizadas |
| `results/tables/` | Parámetros, calidad, eventos y manifiesto |
| `docs/` | Protocolo, diccionario, métodos, referencias, uso de IA y contribuciones |
| `report/` | Informe y borradores por sección |
