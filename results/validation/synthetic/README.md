# Validación sintética de dinámica

Se usó el generador de A con sus opciones predeterminadas, calibración exclusivamente
en fit y predicción continua en la ventana validation. No son observaciones reales.
La primera lectura de cada una de seis macetas inicializa su trayectoria y queda
fuera de los errores; las otras 132 lecturas se comparan en sus instantes exactos.
Los eventos registrados son entradas; no se aplica una política contrafactual.

Agregado por observaciones: MAE 0.373594 mL, RMSE 0.485930 mL, sesgo -0.135304 mL.
Estos errores son una comprobación sintética de integración y no prueban capacidad
predictiva en plantas reales. `errors.csv` incluye los errores por maceta y ALL;
`comparisons.csv` conserva filas de procedencia y errores individuales.
`trajectory.csv`, `events.csv` y `validation_manifest.json` permiten auditar el cálculo.
Las figuras PNG/PDF se encuentran en `figures/`.

Los datos sintéticos de entrada no se versionan por la regla existente de `.gitignore`.
Para regenerarlos y reproducir las salidas se usan los comandos completos de
`docs/validation.md`. El manifiesto registra sus hashes para comprobar identidad.
La validación real sigue pendiente de mediciones y particiones congeladas.
