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
| 2026-11-06 | Área C (Eliazar Canastuj), preparación asistida por Codex; revisión humana pendiente | PSO, política por umbrales, auditoría independiente, integración CLI y pruebas | `src/macetas/pso.py`, `constraints.py`, `optimization.py`, `policies.py`, `tests/test_optimization.py`; sin commit |
| 2026-11-06 | Área C, preparación asistida por Codex | Configuraciones, 30 búsquedas por variante, política sintética congelada y trazabilidad | `configs/pso.json`, `configs/demo_pso.json`, `results/optimization/synthetic/`; sin commit |
| 2026-11-06 | Área C, preparación asistida por Codex | Investigación, revisión de A, sección de informe y material de exposición | `docs/optimization.md`, `docs/review_A_by_C.md`, `report/secciones/C_optimizacion.md`, `presentation/C_guion.md`, `docs/ai_usage.md`; revisión por B pendiente, tiempo humano por registrar |
| 2026-11-10 | Nelson Escalante | Datos públicos reales (Chase 2026): conversión, calibración por maceta y validación; corrección de eventos vacíos en calibración, origen `public` en modelo y validación, origen y figura 4 en gráficas | `src/macetas/public_data.py`, `data/reference/chase2026_enset/`, `results/calibration/public_enset/`, `results/validation/public_enset/`, `tests/test_public_data.py` |
| 2026-11-10 | Nelson Escalante | Tabla de la Parte 6 (referencia real, base y mejora) con el caso documentado de Lieth y la validación con Chase (2026) | `src/macetas/comparison_table.py`, `data/reference/lieth_ucdavis/`, `results/tables/comparacion_real.md`, `tests/test_comparison_table.py` |
| 2026-11-10 | Nelson Escalante | Revisión técnica cruzada del área D, incluida la prueba del panel | `docs/review_D_by_A.md` |
