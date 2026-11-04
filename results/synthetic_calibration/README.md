**Calibración con datos SINTÉTICOS**

Parámetros obtenidos al calibrar el conjunto sintético de `src/macetas/synthetic_data.py` (semilla 20260001). Sirven para desarrollar y probar el simulador, PSO y los experimentos mientras no hay mediciones. **No son mediciones ni validación contra la realidad**: todos los archivos dicen `data_origin = synthetic` y el simulador solo los acepta con `--allow-synthetic`.

| Archivo | Contenido |
| --- | --- |
| `parametros_modelo.json` | Entrada del simulador (`--parameters`) |
| `parametros.csv`, `seleccion_modelos.csv`, `eventos_riego.csv` | Tablas de la calibración |
| `calibracion_manifest.json` | Configuración, hashes, versiones y semillas |
| `parametros_verdaderos.json` | Parámetros con los que se generaron los datos, para comparar lo recuperado |
| `simulacion_demo/` | Corrida de 7 días con `configs/demo_base.json` |

Valores verdaderos frente a calibrados (modelo agrupado `blocks_linear`): `a` 2.5 → 2.394 mL/h (las macetas varían ±10 % alrededor de 2.5), `b` −0.006 → −0.0051 1/h, `q_night` 0.35 → 0.355.

Regenerar:

```bash
python -m src.macetas make-synthetic --out data/synthetic
python -m src.macetas calibrate --config configs/model.json --data-config data/synthetic/data_config.json
python -m src.macetas simulate --parameters results/synthetic_calibration/parametros_modelo.json --base configs/demo_base.json --allow-synthetic --out results/synthetic_calibration/simulacion_demo
```

Los archivos se copian desde `data/synthetic/salidas/tables/` (carpeta ignorada por git). Cuando existan mediciones, los parámetros reales salen en `results/tables/parametros_modelo.json` y reemplazan a estos.
