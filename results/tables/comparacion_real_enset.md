**Comparación con escenarios reales (Parte 6)**

Tabla generada por `python -m src.macetas.comparison_table`. No contiene valores ajustados a mano.

| Métrica | Unidad | Referencia real | Simulación base | Simulación mejorada | Cambio absoluto (mejorada − base) | Cambio porcentual |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Agua aplicada por maceta | mL/maceta/día | 273.1 | 369.6 | 298.0 | -71.6 | -19.4 |
| Déficit máximo | mL | 517.0 | 363.8 | 508.0 | 144.1 | 39.6 |
| Reducción del agua aplicada respecto de la base | % | 28.2 | 0.0 | 19.5 | 19.5 | — |
| Ejecuciones que cumplen las restricciones | % | — | 100.0 | 96.7 | -3.3 | — |
| Pérdida de agua en secado sin riego | mL/maceta/día | 81.0 | 113.3 | — | 32.3 | 39.8 |

En la última fila el cambio es el error del modelo base frente a la referencia real (predicho − observado).

**Fuentes por fila**

1. Agua aplicada por maceta. Referencia: Chase (2026): plantas control [4, 8], 2024-07-24 a 2024-08-05; riego estimado por la masa (cota inferior), medias por planta [202.2, 344.0]. Simulación: B0/O0, 30 réplicas, 7 días, origen public, maceta E12.
2. Déficit máximo. Referencia: Chase (2026): plantas control, respecto de la masa al inicio del periodo; define el límite operacional (520 mL). Simulación: Media de las réplicas.
3. Reducción del agua aplicada respecto de la base. Referencia: Lieth (otras especies): tensiómetro frente a productor, mediana (rango 3.7–65.3 %). Simulación: Media de ahorros pareados O0 frente a B0 en pares factibles (DE 1.5 %).
4. Ejecuciones que cumplen las restricciones. Referencia: No reportado por las fuentes. Simulación: Auditor independiente de restricciones.
5. Pérdida de agua en secado sin riego. Referencia: Chase (2026): ventana de validación, 21 macetas, origen public. Simulación: Modelo por maceta calibrado en la ventana de ajuste; MAE 172 mL, sesgo +157 mL. La política no actúa sin riegos.

**Correspondencia y alcance**

- Las simulaciones usan la calibración `public` de Chase (2026), maceta representativa E12, el mismo sistema que la referencia real. La base aplica 369.6 mL/maceta/día frente a 273.1 estimados en las plantas control (medias por planta 202, 344). El riego real es una cota inferior y corresponde a otras dos plantas, con otros genotipos.
- La reducción simulada en pares factibles (19.5 %) se contrasta con el ahorro que Lieth documentó al pasar de un riego fijo a uno guiado por mediciones (3.7–65.3 %, mediana 28.2 %), en otras especies. Es un contraste de orden de magnitud, no una validación de la mejora.
- Factibilidad: O0 cumple las restricciones en 96.7 % de las réplicas y ambas políticas a la vez en 96.7 % de los pares; el ahorro solo se reporta en pares factibles (con todos los pares sería 19.4 %).
- Correspondencia del modelo base con mediciones reales (Chase, 2026): en secado sin riego predice 113.3 mL/maceta/día frente a 81.0 observados (MAE 172 mL, sesgo +157 mL), con mayor error donde la validación extrapola a déficits mayores que los del ajuste.
- Toda la mejora es simulada. No se implementó ni midió la política optimizada en plantas reales, por lo que no se afirma una reducción observada.
