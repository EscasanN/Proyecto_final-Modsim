**Datos públicos: pesajes de macetas de *Ensete ventricosum* (Chase, 2026)**

Responsable de la conversión: Nelson Escalante.

**Fuente**

| Campo | Valor |
| --- | --- |
| Cita | Chase, R. R. (2026). *Transpiration monitoring reveals diverse drought coping strategies in wild and cultivated enset (Ensete ventricosum)* [Conjunto de datos]. Zenodo |
| DOI | [10.5281/zenodo.23213759](https://doi.org/10.5281/zenodo.23213759) |
| Licencia | CC BY 4.0 (uso con atribución) |
| Fecha de consulta | 2026-11-10 |
| Archivo usado | `Phenospex_data.csv`, SHA-256 `f3dc9a70477d8a9423d665a813c3391f5db9eb4282338ff89050f93d52c36336` |
| Contenido | Masa de cada maceta cada 15 min en una plataforma gravimétrica Phenospex, del 2024-07-11 al 2024-08-06 |
| Plantas | 24; desde el 2024-07-24, 22 pasan de control a estrés hídrico |

Son **mediciones reales de terceros**, de otra especie, otra plataforma y otro lugar. Se identifican con `data_origin = public` y no sustituyen las observaciones propias del montaje de *Crassula ovata*. Se emplean para comprobar con datos reales la forma del modelo de pérdidas y el procedimiento de calibración y validación.

**Obtención**

Los originales no se versionan; se descargan y se verifican por hash:

```bash
mkdir -p data/reference/chase2026_enset/original
curl -L -o data/reference/chase2026_enset/original/Phenospex_data.csv "https://zenodo.org/records/23213759/files/Phenospex_data.csv?download=1"
python -m src.macetas import-public
```

`import-public` rechaza el archivo si su SHA-256 no coincide con el publicado. La salida en `converted/` sí se versiona.

**Conversión** (`src/macetas/public_data.py`)

| Decisión | Motivo |
| --- | --- |
| Solo el periodo de estrés (2024-07-24 a 2024-08-06) de las plantas que pasaron a estrés | Secado continuo, sin riegos de la plataforma |
| Exclusión de plantas con una subida neta mayor que 50 g en 3 h | Aportes de agua que la fuente no documenta. Se excluyó la planta `id 13` |
| Lectura más cercana a las 07:00, 13:00 y 19:00, a menos de 15 min | Misma frecuencia que el protocolo propio |
| `M_ref` = primera masa del periodo de estrés | Referencia operacional; no es una masa drenada como en el protocolo propio |
| Hora de reloj con desfase nominal −06:00 | La fuente no declara zona horaria; el simulador exige `America/Guatemala` (sin horario de verano). No indica que el ensayo ocurriera en Guatemala |
| Ajuste: primeros 7 días; validación: los 7 siguientes | Ventanas completas y consecutivas, fijadas antes de calibrar |
| Tolerancia de masa 2.38 g | Sin verificación de balanza en la fuente; `3·√2·0.56 g`, con 0.56 g = desviación de las diferencias de 15 min entre 01:00 y 04:59, cota superior del ruido |

Resultado: 21 macetas (`E01`–`E31`, según el `id` original), 793 lecturas, 0 errores de calidad y 61 advertencias de aumento de masa. Las advertencias corresponden a ganancias nocturnas de 2 a 19 g entre las 19:00 y las 07:00, presentes en la fuente. Se conservan sin corregir; su causa (humedad, condensación o deriva de las celdas de carga) no se puede determinar con los datos.

**Reproducción completa**

```bash
python -m src.macetas import-public
python -m src.macetas validate-data --config data/reference/chase2026_enset/converted/data_config.json
python -m src.macetas calibrate --config configs/model_public_enset.json
python -m src.macetas.validation --data-config data/reference/chase2026_enset/converted/data_config.json --parameters data/reference/chase2026_enset/converted/salidas/tables/parametros_modelo.json --out results/validation/public_enset
python -m src.macetas.plots --validation results/validation/public_enset --validation-only
```

Tablas de calibración: `results/calibration/public_enset/`. Validación y figuras: `results/validation/public_enset/`.
