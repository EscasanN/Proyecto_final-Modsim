**Validación con datos públicos reales (Chase, 2026)**

Mediciones reales de terceros (`data_origin = public`): 21 macetas de *Ensete ventricosum* en secado continuo, pesadas cada 15 min y muestreadas a las 07:00, 13:00 y 19:00. No son observaciones del montaje de *Crassula ovata*. Procedencia y conversión: `data/reference/chase2026_enset/README.md`.

**Procedimiento**

- Calibración con la ventana `fit` (7 días) y parámetros por maceta (`configs/model_public_enset.json`). La elección por maceta se tomó con datos de ajuste: en 15 de 21 macetas el IC95 de `a` excluye el valor agrupado.
- Validación con la ventana siguiente (7 días), sin recalibrar: se inicia con la primera lectura y se predice de forma continua, sin reiniciar con observaciones posteriores (`src/macetas/validation.py`).
- No hubo riegos en el periodo; se valida la dinámica de secado.

**Ajuste (ventana fit)**

| Ámbito | Modelo | a [mL/h] | b [1/h] | q noche | RMSE [mL] | Intervalos |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Agrupado | blocks_linear | 21.55 (IC95 14.30–24.67) | −0.0050 (IC95 −0.0078–0.0000) | ≈ 0 | 44.8 | 361 |

La pérdida nocturna es prácticamente nula y la pérdida diurna disminuye al aumentar el déficit (`b < 0`), lo que coincide con la forma prevista del modelo. Por maceta, el modelo seleccionado fue `blocks_linear` en 16 macetas y `blocks` (sin dependencia del déficit) en 5.

**Error de validación** (`errors.csv`)

| Grupo | Macetas | MAE [mL] (mediana) | MAE / déficit medio (mediana) |
| --- | ---: | ---: | ---: |
| Modelo con dependencia del déficit (`blocks_linear`) | 16 | 59.7 | 3.7 % |
| Modelo sin dependencia del déficit (`blocks`) | 5 | 597.0 | 27.7 % |
| Todas (agregado por observaciones) | 21 | 172.4 (RMSE 308.3, sesgo +157.3) | 9.7 % |

**Interpretación**

- En todas las macetas el déficit de validación supera el máximo observado durante el ajuste: la validación es una extrapolación hacia condiciones más secas.
- Donde el ajuste identificó la reducción de pérdidas con el secado, el modelo extrapola con un error mediano de 3.7 % del déficit.
- Con solo 7 días de ajuste, el criterio AICc eligió en 5 macetas el modelo sin `b`. Ese modelo mantiene la pérdida constante y sobrestima el secado posterior (sesgo positivo de 360 a 660 mL). No se cambió la regla de selección después de ver estos errores, para no usar la validación en la elección del modelo.
- Consecuencia para el montaje propio: el ajuste debe cubrir el rango de déficit en que operarán las políticas, y las predicciones fuera de ese rango deben tratarse como extrapolación.

**Archivos**

`comparisons.csv` (cada lectura comparada), `errors.csv` (por maceta y ALL), `trajectory.csv`, `events.csv`, `validation_manifest.json` (hashes, partición, `public_reference_validation: true`). Figuras (`python -m src.macetas.plots --validation results/validation/public_enset --validation-only`): `figures/01_system` (primera maceta, E01) y `figures/04_validation_all` (todas las macetas).
