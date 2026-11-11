**Datos originales**

> **Trabajo futuro.** Este documento describe el montaje propio de *Crassula ovata* que no se llegó a medir. El sistema real de la entrega es el ensayo de Chase (2026); ver `docs/sistema_enset.md`.

Mediciones propias del equipo (`data_origin = observed`), según [docs/protocol.md](../../docs/protocol.md) y [docs/data_dictionary.md](../../docs/data_dictionary.md).

- `macetas.csv`: una fila por maceta, con su masa de referencia drenada.
- `observaciones.csv`: una fila por lectura.
- `balanza.csv`: verificaciones de repetibilidad de la balanza.

Se agregan filas conservando los registros originales. Las mediciones no se sobrescriben, reordenan ni completan con estimaciones. El formato y la coherencia de los datos se comprueban mediante `python -m src.macetas validate-data`.
