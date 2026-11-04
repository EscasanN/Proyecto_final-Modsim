**Distribución de trabajo y contribuciones**

| Integrante | Responsabilidad |
| --- | --- |
| Nelson Escalante | Datos, protocolo y calibración |
| Nina Nájera | Modelo, integradores y simulación |
| Eliazar Canastuj | Optimización y política de riego |
| Diego Ramirez | Experimentos, validación y resultados |

**Aportes registrados**

| Fecha | Integrante | Aporte | Evidencia |
| --- | --- | --- | --- |
| 2026-11-03 | Nelson Escalante | Protocolo de medición y diccionario de datos | `docs/protocol.md`, `docs/data_dictionary.md`, commit `483e37c` |
| 2026-11-03 | Nelson Escalante | Carga, controles de calidad, calibración, bloques horarios y generador sintético | `src/macetas/data_io.py`, `calibration.py`, `time_blocks.py`, `synthetic_data.py`, pruebas iniciales, commit `483e37c` |
| 2026-11-03 | Nina Nájera | Corrección de campos opcionales vacíos | `src/macetas/data_io.py`, commit `285beaa` |
| 2026-11-03 | Nina Nájera | Balance de agua, Euler, RK4, eventos, política fija e interfaz del simulador | `src/macetas/model.py`, `integrators.py`, `policies.py`, `simulator.py`, `simulation_io.py`, commit `621be50` |
| 2026-11-03 | Nina Nájera | Casos conocidos, conservación y convergencia | `src/macetas/verification.py`, `tests/test_integrators.py`, `tests/test_simulator.py` |
| 2026-11-03 | Nina Nájera | Precisión de horarios y trazabilidad de calibración | `src/macetas/time_blocks.py`, `calibration.py`, `synthetic_data.py`, pruebas de horarios, commit `8a62bad` |
| 2026-11-03 | Nina Nájera | Formulación, diagrama, límites del modelo y comandos de reproducción | `docs/model.md`, `docs/references.bib`, `README.md` |
| 2026-11-04 | Nelson Escalante | Calibración sintética de referencia para el simulador | `results/synthetic_calibration/`, commit `65b0127` |
| 2026-11-04 | Nelson Escalante | Especie, fuentes de manejo, prueba de sustrato superficial, hoja de registro y turnos | `docs/especie.md`, `docs/hoja_registro.md`, `docs/protocol.md`, `top_dry_thresholds` en `calibration.py` |
