# Calibración de la pérdida de agua

**Responsable:** Nelson Escalante · **Código:** `src/macetas/calibration.py`, `src/macetas/time_blocks.py` · **Revisor:** C

## 1. Qué se estima

Entre riegos, el déficit evoluciona según

$$\frac{dD}{dt} = q(t)\,\max(0,\ a + bD)$$

| Símbolo | Unidad | Significado |
| --- | --- | --- |
| `D` | mL | Déficit respecto de `M_ref` |
| `a` | mL/h | Pérdida con `D = 0` en el bloque de referencia |
| `b` | 1/h | Cambio de la pérdida con el déficit (`b < 0`: un sustrato más seco pierde menos) |
| `q_k` | — | Factor del bloque horario `k`; `q` del primer bloque = 1 para que `a` sea identificable |

Es una aproximación empírica local, no una ley fisiológica. No se extrapola fuera del rango de déficit observado en el ajuste (`deficit_min_fit`, `deficit_max_fit` en `parametros.csv`).

## 2. Datos que entran

Solo **intervalos de secado** de la fase `fit`: pares de lecturas consecutivas de una maceta tales que

- la primera es `post_drainage` o `no_irrigation` y la segunda es `pre_irrigation` o `no_irrigation`;
- ninguna fila de riego de esa maceta (con cualquier marca de calidad) cae entre ellas;
- ambas son utilizables (masa presente, sin error de calidad, `quality_flag` distinto de `bad`);
- ambas pertenecen a la ventana `fit` y la duración está entre `min_interval_h` y `max_interval_h`.

`fit_model` rechaza cualquier intervalo de otra fase (protección contra fuga de información desde validación).

## 3. Ajuste

Para cada intervalo, el déficit final se predice con la **solución exacta por tramos** de la ecuación partiendo del déficit inicial observado. En un tramo de `h` horas con factor `q`:

$$D_1 = D_0 + (a + bD_0)\,\frac{e^{bqh}-1}{b} \quad (b\neq 0), \qquad D_1 = D_0 + a\,q\,h \quad (b = 0)$$

Los cortes de bloque (por ejemplo 06:00 y 18:00) dividen el intervalo en tramos. Así, un intervalo de 19:00 a 07:00 se trata sin aproximar. Los parámetros minimizan la suma de cuadrados de `D_1,pred − D_1,obs` (scipy `least_squares`, método `trf`, con límites de `configs/model.json`).

El déficit inicial también tiene error de medición (problema de errores en las variables). Con `σ_lectura` pequeño frente a la pérdida entre revisiones el sesgo es despreciable; si no lo es, se discute como limitación.

**Biblioteca vs. equipo:** SciPy resuelve el problema de mínimos cuadrados. La selección de intervalos, el operador de predicción por tramos, la normalización de `q`, la selección de modelo y el bootstrap son código del equipo.

## 4. Selección de modelo

| Modelo | Parámetros libres |
| --- | --- |
| `constant` | `a` |
| `blocks` | `a`, `q` de los bloques no de referencia |
| `blocks_linear` | `a`, `b`, `q` de los bloques no de referencia |

Se calcula el AICc de cada uno (`n·ln(RSS/n) + 2k + 2k(k+1)/(n−k−1)`). Se elige **el de menos parámetros entre los que quedan a menos de `tolerance` (2) del menor AICc**. La regla se fija antes de ver los datos, así que un modelo complejo solo entra si mejora claramente.

El ajuste se hace agrupado (`pooled`) y por maceta. `configs/model.json → calibration.scope` indica cuál exporta el equipo como principal. Si las macetas difieren claramente (los intervalos de confianza por maceta no se solapan), se recomienda usar parámetros por maceta.

## 5. Incertidumbre

- **Error estándar** a partir del jacobiano en el óptimo (`se`).
- **Intervalo al 95 % por bootstrap de días completos**: se remuestrean días (no intervalos), porque los intervalos de un mismo día comparten condiciones y no son independientes. Se usa la semilla `bootstrap.seed` (+ índice del ámbito) y se registra en el manifiesto. Con menos de 3 días no se calcula; con pocos días el intervalo es poco fiable y se reporta así.
- **Error de medición**: `σ_lectura` de la verificación de balanza.

## 6. Diagnóstico de los riegos

`eventos_riego.csv` contrasta cada riego de piloto y ajuste con la regla ideal del modelo (`Q = max(0, I − D⁻)`, `D⁺ = max(0, D⁻ − I)`):

- `drainage_residual_ml`: drenaje observado − ideal;
- `deficit_post_residual_ml`: déficit tras el drenaje observado − ideal (incluye la pérdida esperada durante el evento);
- `apparent_loss_ml`: pérdida que el balance atribuye al lapso del evento.

Si los residuos son sistemáticamente grandes frente a `σ_lectura`, la hipótesis de drenaje instantáneo no se sostiene y B debe considerar un estado de agua excedente (plan §6.3). Los eventos de validación no se usan aquí.

## 7. Qué recibe cada integrante

| Quién | Archivo | Para qué |
| --- | --- | --- |
| B | `parametros_modelo.json` (`pooled`, `per_pot`, `time_blocks`) | Función de pérdidas del simulador; `time_blocks.py` para los cortes de bloque |
| B | `predict_deficit` | Referencia exacta para verificar Euler y RK4 |
| C | `measurement.sigma_deficit_ml` | Error de medición al simular `D_hat` |
| D | `observed_range_fit`, `ci95`, partición congelada | Validación, sensibilidad y límites de extrapolación |

## 8. Reproducir

```bash
python -m src.macetas validate-data
python -m src.macetas calibrate --config configs/model.json
```

Con datos sintéticos de prueba:

```bash
python -m src.macetas make-synthetic --out data/synthetic
python -m src.macetas calibrate --config configs/model.json --data-config data/synthetic/data_config.json
```

Las salidas sintéticas quedan en `data/synthetic/salidas/`, separadas de las reales, y todas sus filas dicen `data_origin = synthetic`.
