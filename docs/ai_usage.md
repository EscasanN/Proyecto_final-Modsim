# Uso de herramientas de inteligencia artificial

El enunciado exige declarar el uso de IA. Cada integrante registra aquí lo que usó, para qué y cómo lo verificó.

| Fecha | Integrante | Herramienta | Uso | Verificación humana |
| --- | --- | --- | --- | --- |
| 2026-11-03 | Nelson Escalante | Claude Code (Anthropic, modelo Claude Opus 5.5) | Primera versión de `data_io.py`, `time_blocks.py`, `calibration.py`, `synthetic_data.py`, la CLI, las pruebas de `tests/` y los borradores de `docs/protocol.md`, `docs/data_dictionary.md`, `docs/calibration.md` y `report/secciones/A_contexto_datos.md`, a partir del plan de trabajo del equipo. Consulta de metadatos de [R1] y [R2]. | Los datos fueron verificados y los programas funcionan de manera correcta, segun lo esperado :)

Ningún dato de `data/raw/` fue generado por IA. Los datos sintéticos se generan con `src/macetas/synthetic_data.py`, están marcados como `synthetic` y no se usan como validación.
