**Sistema real del proyecto: ensayo documentado de *Ensete ventricosum* (Chase, 2026)**

Responsable: Nelson Escalante, con revisión de B, C y D.

**Cambio de alcance**

No fue posible completar las mediciones propias del montaje de *Crassula ovata* dentro del plazo. Por eso se adoptó como sistema real un ensayo documentado y público: la plataforma gravimétrica de Chase (2026, Zenodo, doi:10.5281/zenodo.23213759, CC BY 4.0), con macetas de *Ensete ventricosum* pesadas cada 15 min. Las mediciones son de terceros y se identifican con `data_origin = public`. El equipo no midió ni cultivó estas plantas. El protocolo de *Crassula ovata* (`docs/protocol.md`, `docs/especie.md`) se conserva como diseño para trabajo futuro.

Con este cambio, la calibración, la validación, la optimización y los experimentos se apoyan en el mismo sistema real.

**Entradas derivadas de los datos**

Todas las entradas se obtienen de la ventana de ajuste o de las plantas control, nunca de la ventana de validación.

| Entrada | Valor | Procedimiento | Archivo |
| --- | --- | --- | --- |
| Parámetros de pérdida | Por maceta, `blocks_linear` en 16 de 21 | Calibración en la ventana fit (7 días) | `results/calibration/public_enset/` |
| Maceta representativa | E12: a = 28.23 mL/h, b = −0.0102 1/h, q noche = 0.025 | La más cercana a la mediana de (a, b, q noche), en unidades estandarizadas, entre las 16 macetas `blocks_linear` | `configs/pso_enset.json` (`pot_id`) |
| Variabilidad diaria | CV 0.083 | Desviación entre días de la mediana, entre macetas, de la razón pérdida observada / predicha (07:00 a 07:00, 5 días fit) | `configs/pso_enset.json` (`forcing.daily_cv`) |
| Error de lectura | 0.397 mL | Desviación de diferencias nocturnas de 15 min dividida entre √2; cota superior | `data/reference/chase2026_enset/converted/data_config.json` |
| Riego real de referencia | 273.1 mL/maceta/día (202.2 y 344.0) | Plantas que permanecen en control (id 4 y 8): suma de subidas de masa > 5 g entre 01:00 y 07:59, del 24-jul al 5-ago; cota inferior | `referencia_control_riego.csv` y `control_reference` en `data_config.json` |
| Límite operacional `D_seguro` | 520 mL | Mayor déficit de las plantas control respecto de su masa al inicio del periodo (517 mL), redondeado a 5 mL | `configs/base_enset.json` |
| Dosis máxima y presupuesto diario | 750 mL | Mayor riego diario estimado de las plantas control (747 mL), redondeado | `configs/base_enset.json` |
| Política base | 325 mL diarios a las 07:00 | Riego diario fijo como el de la plataforma; dosis = pérdida de 24 h de E12 desde D = 0 (326.4 mL), redondeada a 5 mL | `configs/base_enset.json` |
| Horizonte | 7 días, D inicial = 0 | Mismo largo que las ventanas de ajuste y validación | `configs/base_enset.json` |

El intervalo de operación (0 a 520 mL) queda dentro del rango de déficit observado al calibrar E12 (5 a 1628 mL), por lo que las simulaciones de política no extrapolan el modelo de pérdidas.

**Interpretación del límite**

`D_seguro` representa el régimen bien regado de la fuente: ninguna política puede secar la maceta más de lo que la plataforma permitió en sus plantas control. No es un umbral fisiológico de la especie. Se aplica por igual a la base y a la política optimizada.

**Reproducción**

```bash
python -m src.macetas import-public
python -m src.macetas calibrate --config configs/model_public_enset.json
python -m src.macetas optimize --config configs/pso_enset.json
python -m src.macetas.experiments --config configs/experiments_enset.json
python -m src.macetas.comparison_table --experiments results/experiments/public_enset --control data/reference/chase2026_enset/converted/data_config.json --name comparacion_real_enset
```

Los resultados de `calibrate` se copian de `data/reference/chase2026_enset/converted/salidas/tables/` a `results/calibration/public_enset/`, que es la ruta que usan la optimización y los experimentos.
