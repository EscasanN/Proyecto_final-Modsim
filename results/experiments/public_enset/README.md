**Optimización y evaluación final con el sistema real (Chase, 2026)**

Ejecución del 2026-11-11. Modelo calibrado con mediciones reales públicas (`data_origin = public`), maceta representativa E12, política base y límites derivados de los datos (`docs/sistema_enset.md`). Las políticas se evalúan por simulación; ninguna se aplicó a plantas reales.

**Búsqueda (C, `results/optimization/public_enset/`)**

90 corridas (30 por variante, 60 evaluaciones lógicas cada una), 2 escenarios de búsqueda y 3 de selección de 7 días, CV diario 0.083 y error de lectura 0.397 mL.

| Variante | Factibles en búsqueda y selección | Agua de selección, media ± DE [mL] |
| --- | ---: | ---: |
| PSO, inercia 0.7 | 11/30 | 2091.2 ± 16.2 |
| PSO, inercia 0.4 | 6/30 | 2091.7 ± 16.6 |
| Búsqueda aleatoria | 10/30 | 2095.8 ± 14.2 |

Política congelada (PSO 0.4, la de menor agua de selección entre las factibles): activación 365 mL, objetivo 350 mL, dosis máxima 150 mL. En selección aplicó 2077.6 mL frente a 2589.4 mL de la base, con un déficit máximo de 513.5 mL (límite 520 mL). PSO y la búsqueda aleatoria logran valores semejantes; la evidencia no muestra superioridad de PSO.

**Evaluación final (D, esta carpeta)**

30 semillas reservadas (13001–13030), sin volver a optimizar. Valores por maceta en 7 días; el agua total incluye la reposición final al déficit inicial.

| Condición | Agua total [mL] | Reposición final [mL] | Drenaje [mL] | Déficit máximo [mL] | Tiempo sobre el límite [h] | Factibles |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| B0 base, pérdidas normales | 2586.9 ± 30.9 | 311.9 | 324.2 | 363.8 | 0.00 | 30/30 |
| O0 optimizada, pérdidas normales | 2085.7 ± 54.0 | 356.1 | 0.0 | 508.0 | 0.06 | 29/30 |
| B1 base, pérdidas +20 % | 2845.8 ± 42.1 | 570.8 | 286.0 | 586.6 | 28.65 | 1/30 |
| O1 optimizada, pérdidas +20 % | 2478.4 ± 62.7 | 370.9 | 0.0 | 542.2 | 4.78 | 0/30 |

**Interpretación**

- Con pérdidas normales, ambas políticas son factibles en 29 de 30 pares. En esos pares la optimizada reduce el agua en 503 ± 38 mL por maceta en 7 días (19.5 % ± 1.5 %); con los 30 pares, 501 mL (19.4 %). La reducción proviene de eliminar el drenaje: la base repone a diario más agua de la que la maceta retiene y pierde 324 mL por drenaje.
- La mejora se obtiene manteniendo la maceta más seca (déficit máximo 508 frente a 364 mL), dentro del límite del régimen bien regado de la fuente. Con `b < 0`, el modelo predice menor pérdida a mayor déficit. Esto no demuestra que ese estado sea adecuado para la planta.
- Con pérdidas +20 % ninguna de las dos políticas fijadas para condiciones normales es robusta: la base supera el límite en 29 de 30 réplicas y la optimizada en todas, aunque por menos tiempo (4.8 frente a 28.7 h). Ambas tendrían que reajustarse si la demanda aumenta.
- El margen de la política optimizada es estrecho (un caso inviable con pérdidas normales); una aplicación práctica requeriría un margen de seguridad.

**Reproducción**

```bash
python -m src.macetas optimize --config configs/pso_enset.json
python -m src.macetas.experiments --config configs/experiments_enset.json
python -m src.macetas.plots --experiments results/experiments/public_enset
```

Figuras en `figures/`. La tabla de la Parte 6 está en `results/tables/comparacion_real_enset.md`.
