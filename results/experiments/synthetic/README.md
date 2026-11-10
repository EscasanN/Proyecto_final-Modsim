# Evaluación final sintética

Estos resultados usan exclusivamente la calibración sintética existente de A,
la base hipotética de B y la política congelada sintética de C. No son mediciones
ni validación real. Se generaron 30 realizaciones por condición, 120 ejecuciones,
con las semillas 13001–13030 reservadas; no se ejecutó PSO.

| Condición | Agua total media [mL] | DE muestral [mL] | Ejecuciones factibles |
| --- | ---: | ---: | ---: |
| B0 | 310.200 | 3.199 | 30/30 |
| O0 | 227.227 | 7.037 | 26/30 |
| B1 | 333.948 | 6.812 | 30/30 |
| O1 | 270.245 | 8.410 | 0/30 |

El menor consumo de O incluye reposición final; no demuestra una mejora
operacional aceptable porque O incumple restricciones en evaluación final,
especialmente con pérdidas aumentadas. No se reajustó la política con estos datos.
Los ahorros aritméticos de `paired.csv` y `paired_summary.csv` deben interpretarse
junto con la factibilidad, sin seleccionar solo las semillas favorables.
El fracaso de generalización es un resultado experimental, no un error que deba
ocultarse volviendo a optimizar con las semillas reservadas.

`manifest.json` identifica entradas, fuentes, semillas y configuraciones completas.
`runs.csv`, `summary.csv`, `paired.csv`, `paired_summary.csv`, `balance.csv`,
`trajectory.csv`, `events.csv` y `evaluation_scenarios.json` son regenerables.
`figures/` contiene las tres figuras en PNG y PDF. Los tiempos de pared varían.

```powershell
python -m src.macetas.experiments --config configs/demo_experiments.json --allow-synthetic
python -m src.macetas.plots --experiments results/experiments/synthetic
```

El diseño y la validación independiente se describen en `docs/validation.md`.
