**Comparación con escenarios reales (Parte 6)**

Tabla generada por `python -m src.macetas.comparison_table`. No contiene valores ajustados a mano.

| Métrica | Unidad | Referencia real | Simulación base | Simulación mejorada | Cambio absoluto (mejorada − base) | Cambio porcentual |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Agua aplicada por maceta | mL/maceta/día | 296.0 | 44.3 | 32.5 | -11.9 | -26.7 |
| Reducción del agua aplicada respecto de la base | % | 28.2 | 0.0 | 26.8 | 26.8 | — |
| Ejecuciones que cumplen las restricciones | % | — | 100.0 | 86.7 | -13.3 | — |
| Pérdida de agua en secado sin riego | mL/maceta/día | 81.0 | 113.3 | — | 32.3 | 39.8 |

En la última fila el cambio es el error del modelo base frente a la referencia real (predicho − observado).

**Fuentes por fila**

1. Agua aplicada por maceta. Referencia: Lieth: riego del productor, mediana de 6 experimentos (rango 109–544). Simulación: B0/O0, 30 réplicas, 7 días, origen synthetic.
2. Reducción del agua aplicada respecto de la base. Referencia: Lieth (otras especies): tensiómetro frente a productor, mediana (rango 3.7–65.3 %). Simulación: Media de ahorros pareados O0 frente a B0 en pares factibles (DE 2.2 %).
3. Ejecuciones que cumplen las restricciones. Referencia: No reportado por las fuentes. Simulación: Auditor independiente de restricciones.
4. Pérdida de agua en secado sin riego. Referencia: Chase (2026): ventana de validación, 21 macetas, origen public. Simulación: Modelo por maceta calibrado en la ventana de ajuste; MAE 172 mL, sesgo +157 mL. La política no actúa sin riegos.

**Correspondencia y alcance**

- Las simulaciones usan la calibración `synthetic`; no corresponden a las especies de Lieth. La magnitud del agua aplicada no es comparable; la comparación pertinente es la reducción relativa.
- La reducción simulada en pares factibles (26.8 %) se contrasta con el ahorro que Lieth documentó al pasar de un riego fijo a uno guiado por mediciones (3.7–65.3 %, mediana 28.2 %), en otras especies. Es un contraste de orden de magnitud, no una validación de la mejora.
- Factibilidad: O0 cumple las restricciones en 86.7 % de las réplicas y ambas políticas a la vez en 86.7 % de los pares; el ahorro solo se reporta en pares factibles (con todos los pares sería 26.7 %).
- Correspondencia del modelo base con mediciones reales (Chase, 2026): en secado sin riego predice 113.3 mL/maceta/día frente a 81.0 observados (MAE 172 mL, sesgo +157 mL), con mayor error donde la validación extrapola a déficits mayores que los del ajuste.
- Toda la mejora es simulada. No se implementó ni midió la política optimizada en plantas reales, por lo que no se afirma una reducción observada.
