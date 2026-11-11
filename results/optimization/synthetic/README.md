# Evidencia de C: búsqueda sintética

> **Actualización (2026-11-11).** Ya existen resultados con mediciones reales públicas del sistema adoptado (Chase, 2026): validación en `results/validation/public_enset/`, optimización y experimentos en `results/optimization/public_enset/` y `results/experiments/public_enset/`. Ver `docs/sistema_enset.md`. Las menciones a resultados reales pendientes se refieren a las mediciones propias, que no se realizaron.

Ejecución del 2026-11-06. **Datos y escenarios sintéticos; no son validación
real ni evaluación final.** Se usó la calibración sintética existente de A,
la base demostrativa de B y su simulador sin modificar las ecuaciones físicas.

Reproducir desde la raíz, con las dependencias instaladas:

```powershell
python -m src.macetas optimize --config configs/demo_pso.json --allow-synthetic
```

Se realizaron 90 corridas: 30 por variante, 60 evaluaciones lógicas por corrida
(5400 en total). Se simularon 4331 políticas distintas en búsqueda y 89 en
selección; las repeticiones de una terna efectiva reutilizan caché. Dos escenarios
fijos de búsqueda y tres de selección, siete días cada uno, RK4 y paso .25 h.
Las 30 semillas finales reservadas a D no se generaron ni evaluaron.

| Variante | Corridas | Factibles en búsqueda y selección | Agua de selección, media ± DE (mL) |
| --- | ---: | ---: | ---: |
| PSO, inercia .7 | 30 | 27/30 (90 %) | 228.205 ± 2.135 |
| PSO, inercia .4 | 30 | 24/30 (80 %) | 228.392 ± 1.781 |
| Búsqueda aleatoria | 30 | 30/30 (100 %) | 229.723 ± 1.725 |

La tabla resume la media de tres escenarios de selección de cada solución
devuelta. Su desviación es entre corridas del optimizador, no entre plantas.
Incluye corridas inviables; esas cifras no representan ahorro factible de todas
las corridas. Consultar `pso_runs.csv` para filtrar factibilidad. Los tiempos
están en `search_summary.csv` y dependen de caché caliente y del orden; no se
interpretan como una comparación controlada de velocidad.

## Política congelada de desarrollo

- Activación: **88 mL**; objetivo: **86 mL**; dosis máxima: **46 mL**.
- Revisiones: 07:00, 13:00 y 19:00; resolución: 1 mL; máximo tres riegos/día.
- Límite operacional: 100 mL; presupuesto diario: 300 mL.
- Seleccionada por desempate estable: PSO `.7`, semilla `21002`.
- Agua media en búsqueda: **230.393470 mL**; selección: **226.350916 mL**,
  incluida reposición final.
- Mayor déficit en selección: **99.738420 mL**. Las cinco auditorías de búsqueda
  y selección son factibles. Es un margen estrecho respecto del límite hipotético.
- La base fija sobre el mismo banco de selección fue factible y aplicó
  **309.723174 mL** de media, con el mismo cierre.

La búsqueda aleatoria encontró **el mismo mejor valor de selección**,
226.350916 mL. La evidencia no demuestra superioridad de PSO. La comparación
con la base pertenece al banco usado para elegir la política y está sesgada por
selección; no es una estimación independiente de ahorro ni un resultado real.
El modelo con `b < 0` reduce pérdidas al permanecer más seco; esa predicción
no prueba seguridad fisiológica. Las restricciones son hipotéticas de demostración.

## Comprobaciones realizadas

- Suite completa: **88 pruebas aprobadas**, incluidas las previas de A/B.
- Reejecución de la corrida elegida: misma política, objetivo e historial
  (comparación del historial CSV con tolerancia de representación `1e-14`).
- Comprobación de hashes: código ejecutado coincide con el manifiesto.
- Paso reducido a `.125 h`, sin reoptimizar ni cambiar escenarios de selección:
  factible; agua media **226.350916499082 mL**, diferencia respecto de `.25 h`
  de aproximadamente **2.76e-12 mL**. Solo comprueba estabilidad numérica de
  esta candidata y estos escenarios.
- Caso sin candidata factible cubierto por prueba de integración: no se
  congela una política, se guarda `policy=null`.

`verification.json` contiene la comprobación de esta entrega. Es un archivo de
auditoría posterior, no lo sobrescribe el comando `optimize`; si se cambia la
configuración o el código debe repetirse la comprobación antes de reutilizarlo.

Los demás archivos son salidas regeneradas por `optimize`: historial por
generación, corridas, resumen, escenarios, política y manifiesto. La documentación
de método y entrega a D está en `docs/optimization.md`; D conserva la
responsabilidad de validación, experimentos finales, sensibilidad y figuras.
