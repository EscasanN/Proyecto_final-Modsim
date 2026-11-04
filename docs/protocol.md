**Protocolo de medición y registro**

**Montaje**

Se consideran seis macetas de una misma especie, con sustrato y recipientes comparables. Se registra cada maceta con identificador estable, par, especie, sustrato, ubicación y descripción de la planta. Se elige un lugar protegido de lluvia y se documentan los cambios de exposición.

Se pesa siempre el mismo conjunto: maceta, sustrato y planta, sin bandeja ni plato. Se utiliza una bandeja individual removible para recoger el drenaje, sin permitir su reabsorción. La especie, el sustrato, la ubicación y los instrumentos se documentan en los metadatos del montaje.

**Verificación de balanza**

1. Se coloca la balanza en una superficie firme y nivelada y se espera su estabilización.
2. Se realizan diez pesajes de un objeto estable, retirándolo entre lecturas. Si se dispone de una masa conocida, también se comprueba el sesgo.
3. Se registran lecturas, resolución, objeto, instrumento y fecha en `data/raw/balanza.csv`.
4. Se repite la comprobación antes del piloto y una vez por semana durante el ensayo.

El código calcula la desviación de repetibilidad y `sigma_lectura = sqrt(sd² + resolución²/12)`. Se propone una tolerancia de diferencia de masas de `3*sqrt(2)*sigma_lectura`. La pérdida entre revisiones debería superar unas cinco veces `sigma_lectura`; este criterio debe contrastarse con el piloto. Si no se distingue del ruido, se revisa el instrumento, el tamaño del montaje o la frecuencia de observación.

**Referencia drenada**

Se riega cada maceta de forma controlada hasta obtener drenaje libre. Se pesa a los 5, 10, 15, 20 y 30 minutos, registrando las lecturas intermedias como `drainage_check` y la última como `post_drainage`, vinculadas por un mismo evento. La dosis, el drenaje total y la hora real de aplicación se registran una sola vez en la lectura posterior.

Se identifica el tiempo a partir del cual la variación queda dentro de la tolerancia y se define un tiempo de drenaje común y reproducible. La masa en ese tiempo se registra como `reference_mass_g`, junto con su fecha. Es una referencia operacional del montaje, no una medición universal de capacidad de campo.

La referencia no se redefine diariamente. El crecimiento, la caída de hojas y la pérdida de sustrato deben documentarse y evaluarse antes de interpretar los cambios de peso como agua.

**Rutina de revisión**

Se establecen revisiones a las 07:00, 13:00 y 19:00, hora de Guatemala. Se conserva la hora real de cada pesaje en el registro.

Sin riego se pesa la maceta y se anota una lectura `no_irrigation`. Con riego se registra el peso previo como `pre_irrigation`, se mide la dosis y se anota la hora de aplicación. Al terminar el tiempo de drenaje se mide el agua recogida y se registra el peso como `post_drainage`. Las lecturas del mismo riego comparten `event_id`. Después se retira el drenaje.

Solo la fila `post_drainage` contiene `irrigation_ml`, `drainage_ml` e `irrigation_timestamp`, para evitar duplicaciones.

**Incidentes y faltantes**

| Situación | Registro |
| --- | --- |
| No se pudo pesar | Masa vacía y motivo en `notes` |
| Drenaje no medido | Valor vacío, sin sustituir por cero |
| Derrame, lluvia accidental o pérdida de sustrato | Descripción y marca `suspect` o `bad` |
| Caída de hojas, poda o cambios de ubicación | Nota para evaluar la deriva de masa |
| Balanza con fallas | Marca `bad` y nueva verificación instrumental |

Se conserva cero únicamente cuando se confirmó una cantidad nula. La marca `bad` excluye la lectura del ajuste; `suspect` la conserva identificada para revisión. Las observaciones originales no se completan con valores sintéticos.

**Formato y control**

Se utilizan CSV UTF-8, decimales con punto y fechas ISO 8601 con zona horaria, como `2026-11-10T07:05:00-06:00`. Se conserva la bitácora de cualquier corrección; no se borran ni reemplazan mediciones sin trazabilidad. Antes de registrar cambios se ejecuta:

```powershell
python -m src.macetas validate-data
```

El control comprueba el formato, las fechas, las unidades, las etapas de lectura y la coherencia entre riegos, drenaje y pesajes.

**Turnos**

La rotación por revisión sigue el orden Nelson Escalante, Nina Nájera, Eliazar Canastuj y Diego Ramirez, continuando entre días y fines de semana. Se registra un titular y un suplente por sesión.

**Separación temporal**

Se reserva un piloto para establecer la referencia drenada, los instrumentos y los horarios. Después se separan ciclos completos de ajuste (`fit`) y ciclos posteriores de validación (`validation`). La fase de intervención (`intervention`) se utiliza únicamente después de congelar una política, cuando se realice una comparación física.

Las ventanas se definen en `configs/data.json` y se congelan antes del ajuste final con `frozen: true` y una fecha en `frozen_on`. El código rechaza fases que contradicen las ventanas y el ajuste solo recibe intervalos `fit`.

**Parámetros del ensayo**

| Decisión | Registro |
| --- | --- |
| Especie, sustrato, ubicación y fuente de manejo | Metadatos de macetas y bibliografía |
| Instrumento y error de lectura | `balanza.csv` y tabla de parámetros |
| Masa de referencia y tiempo de drenaje | `macetas.csv`, eventos y diagnóstico de drenaje |
| Horarios y bloques de pérdida | `configs/model.json` y configuración base |
| Ventanas de ajuste y validación | `configs/data.json` |
| Tolerancia de error de validación | Criterio definido antes de observar el error final |
| Límite operacional, dosis y presupuesto diario | `configs/base.json`, con justificación |
| Dosis y horario de referencia | Política base congelada antes de optimizar |

**Registro de cambios**

| Fecha | Cambio | Responsable |
| --- | --- | --- |
| 2026-11-03 | Protocolo, formatos y controles iniciales | Nelson Escalante |
| 2026-11-03 | Coherencia del protocolo con el simulador | Nina Nájera |
