**Comparación con escenarios reales (Parte 6)**

Tabla generada por `python -m src.macetas.comparison_table`. No contiene valores ajustados a mano.

| Métrica | Unidad | Referencia real | Simulación base | Simulación mejorada | Cambio absoluto (mejorada − base) | Cambio porcentual |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Agua aplicada por maceta | mL/maceta/día | 296.0 | 44.3 | 32.5 | -11.9 | -26.7 |
| Agua aplicada con la alternativa guiada por el déficit | mL/maceta/día | 201.5 | — | 32.5 | — | — |
| Reducción del agua aplicada respecto de la base | % | 28.2 | 0.0 | 26.7 | 26.7 | — |
| Ejecuciones que cumplen las restricciones | % | — | 100.0 | 86.7 | -13.3 | — |
| Pérdida de agua en secado sin riego | mL/maceta/día | 81.0 | 113.3 | — | 32.3 | 39.8 |

**Fuentes por fila**

1. Agua aplicada por maceta. Referencia: Lieth: riego del productor, mediana de 6 experimentos (rango 109–544). Simulación: B0/O0, 30 réplicas, 7 días, origen synthetic.
2. Agua aplicada con la alternativa guiada por el déficit. Referencia: Lieth: riego por tensiómetro, mediana (rango 83–422). Simulación: O0.
3. Reducción del agua aplicada respecto de la base. Referencia: Lieth: tensiómetro frente a productor, mediana (rango 3.7–65.3 %). Simulación: Media de ahorros pareados O0 frente a B0 (DE 2.2 %).
4. Ejecuciones que cumplen las restricciones. Referencia: No reportado por la fuente. Simulación: Auditor independiente de restricciones.
5. Pérdida de agua en secado sin riego. Referencia: Chase (2026): ventana de validación, 21 macetas, origen public. Simulación: Modelo calibrado en la ventana de ajuste; MAE 172 mL, sesgo +157 mL. La política no actúa sin riegos.

**Correspondencia y alcance**

- La simulación base y la mejorada usan la calibración de origen `synthetic`; no corresponden a las especies ni a las macetas de Lieth. La magnitud del agua aplicada no es comparable: las macetas de Lieth aplican 109–544 mL/día y la simulación 44.3 mL/día. La comparación pertinente es la reducción relativa.
- La reducción simulada (26.7 %) queda dentro del rango que Lieth observó al pasar de un riego del productor a uno guiado por mediciones (3.7–65.3 %, mediana 28.2 %). Es una coincidencia de orden de magnitud, no una validación de la mejora.
- La mejora simulada no es plenamente factible: O0 cumple las restricciones en 86.7 % de las réplicas y ambas políticas a la vez en 86.7 % de los pares. No se presenta como ahorro equivalente.
- La correspondencia del modelo base con mediciones reales se evaluó con Chase (2026): en secado sin riego predice 113.3 mL/maceta/día frente a 81.0 observados (MAE 172 mL, sesgo +157 mL), con mayor error donde la validación extrapola a déficits más altos que los del ajuste.
- Toda la mejora es simulada. No se implementó ni midió la política optimizada en plantas reales, por lo que no se afirma una reducción observada.
