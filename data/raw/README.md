# Datos originales

Mediciones propias del equipo (`data_origin = observed`), según [docs/protocol.md](../../docs/protocol.md) y [docs/data_dictionary.md](../../docs/data_dictionary.md).

- `macetas.csv`: una fila por maceta, con su masa de referencia drenada.
- `observaciones.csv`: una fila por lectura.
- `balanza.csv`: verificaciones de repetibilidad de la balanza.

Reglas: solo se **agregan** filas; nada se sobrescribe, reordena ni completa con estimaciones. Antes de cada commit, ejecutar `python -m src.macetas validate-data`. Los archivos empiezan vacíos (solo encabezados) hasta que comience el piloto.
