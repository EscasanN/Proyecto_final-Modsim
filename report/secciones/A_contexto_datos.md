**Contexto, datos y calibración**

**Problema y objetivo**

El riego con dosis y horario fijos puede aplicar más agua de la que una maceta perdió, y el exceso sale como drenaje; o puede dejar un déficit elevado antes del riego siguiente. El peso de la maceta permite seguir el agua retenida: entre dos pesajes sin riego, la disminución de masa corresponde casi por completo al agua evaporada y transpirada. Se establece una política fija como referencia para comparar decisiones de riego.

La pregunta de investigación es: ¿puede una política optimizada reducir el agua aplicada por maceta, respecto de un horario fijo razonable, manteniendo el déficit dentro de un intervalo operacional justificado?

La métrica principal es el agua total aplicada, en mL por maceta durante un horizonte común de 7 días, incluida la reposición final al déficit inicial, a minimizar.

**Sistema real**

El sistema real es un ensayo documentado y público: la plataforma gravimétrica de Chase (2026; Zenodo, doi:10.5281/zenodo.23213759, licencia CC BY 4.0), en la que macetas de *Ensete ventricosum* (enset) se pesaron cada 15 min del 11 de julio al 6 de agosto de 2024. Las mediciones son de terceros: el equipo no cultivó ni midió estas plantas. Se identifican en todo el repositorio como `data_origin = public`.

| Elemento | Descripción |
| --- | --- |
| Sistema | Macetas de *Ensete ventricosum* en plataforma Phenospex (Chase, 2026) |
| Entradas | Riegos; condiciones ambientales agrupadas en la pérdida `E` |
| Estado | Déficit `D` respecto de la masa al inicio del periodo de estrés (mL) |
| Salidas | Déficit, agua aplicada y drenaje (mL) |
| Decisión | Cuánto regar en cada revisión (07:00, 13:00, 19:00) |

Se excluyen crecimiento, rendimiento, salud de la planta y generalización a otras especies, plataformas o estaciones. Un intervalo de déficit es una condición operacional, no una demostración de bienestar vegetal.

Como antecedentes se registran el informe de Lieth (UC Davis) sobre riego de macetas con tensiómetros, que reporta agua aplicada por maceta con riego fijo y con riego guiado por mediciones, y el método gravimétrico de Kombala Liyanage et al. (2022).

**Datos y conversión**

La conversión (`src/macetas/public_data.py`) verifica el archivo original por SHA-256 y lo lleva al formato del proyecto (`docs/data_dictionary.md`):

- Se usa el periodo de estrés hídrico, del 24 de julio al 6 de agosto, de las 22 plantas que pasaron de control a estrés: 14 días de secado continuo.
- Se toman las lecturas más cercanas a las 07:00, 13:00 y 19:00.
- Se excluyó una planta (id 13) con aportes de agua no documentados, según una regla aplicada a todas: una subida neta mayor que 50 g en 3 h.
- La referencia de masa es la primera masa del periodo de estrés.
- La fuente no incluye verificación de balanza. El error de lectura (0.40 mL) se estimó del ruido nocturno y se declara como estimación.

Resultado: 21 macetas, 793 lecturas, sin errores de calidad y con 61 advertencias por ganancias nocturnas de 2 a 19 g presentes en la fuente. Las advertencias se conservan sin corregir.

$$D(t)=\frac{M_{ref}-M(t)}{\rho_w},\qquad \rho_w\approx1\ \mathrm{g/mL}.$$

**Partición y calibración**

Los primeros 7 días forman la ventana de ajuste y los 7 siguientes, la de validación; ambas se congelaron antes de calibrar. El código estima `a`, `b` y los factores horarios de `dD/dt = q(t)·max(0, a + bD)` con los intervalos de secado de la ventana de ajuste, usando la solución exacta por tramos. Se comparan tasa constante, tasa por bloques y tasa por bloques con dependencia del déficit, y se selecciona la de menor complejidad entre las que quedan a menos de 2 unidades del AICc mínimo. La incertidumbre se estima por remuestreo de días completos.

En la ventana de ajuste, 15 de 21 macetas tienen un intervalo de confianza del 95 % de `a` que excluye el valor agrupado, por lo que se usan parámetros por maceta. El modelo con dependencia del déficit fue seleccionado en 17 macetas. El ajuste agrupado da `a` = 21.6 mL/h, `b` = −0.0050 1/h y una pérdida nocturna casi nula: la pérdida disminuye cuando la maceta se seca.

**Validación**

La validación predice la ventana reservada sin recalibrar y sin reiniciar con lecturas posteriores. El MAE agregado fue 172 mL (9.7 % del déficit medio). En las 17 macetas con dependencia del déficit, el error mediano fue 3.7 % del déficit (60 mL). En las 4 en que el criterio AICc eligió una pérdida constante, el modelo sobrestimó el secado (error mediano 27.7 %). La causa es que la validación alcanza déficits mayores que los del ajuste y esa forma no reduce la pérdida al secarse. No se modificó la regla de selección después de ver estos errores.

**Entradas de la optimización derivadas de los datos**

Las entradas de la comparación de políticas se obtuvieron de la ventana de ajuste o de las dos plantas que permanecieron en control (bien regadas) durante todo el ensayo (`docs/sistema_enset.md`):

| Entrada | Valor | Origen |
| --- | --- | --- |
| Maceta representativa | E12 (a = 28.2 mL/h, b = −0.0102 1/h) | La más cercana a la mediana de las 17 macetas con dependencia del déficit |
| Variabilidad diaria | CV 0.083 | Razón pérdida observada / predicha entre días de ajuste |
| Riego real de referencia | 273.1 mL/maceta/día | Riego nocturno de la plataforma a las plantas control, estimado por la masa (cota inferior) |
| Límite operacional | 520 mL | Mayor déficit de las plantas control (517 mL) |
| Política base | 325 mL diarios a las 07:00 | Riego diario fijo como el de la plataforma; dosis = pérdida de 24 h de E12 desde D = 0 |

El intervalo de operación (0 a 520 mL) queda dentro del rango de déficit calibrado de E12 (5 a 1628 mL).

**Limitaciones de los datos**

- Los datos son de otro equipo y de una sola plataforma. Las conclusiones no se generalizan a otras especies ni montajes.
- La zona horaria no está declarada en la fuente. Se conserva la hora de reloj con un desfase nominal.
- El riego de las plantas control se infiere de los aumentos de masa y es una cota inferior. Corresponde a dos plantas de genotipos distintos de E12.
- Varias lecturas de una maceta no equivalen a plantas independientes; los intervalos de confianza dependen de 7 días de ajuste.
- El límite operacional representa el régimen bien regado de la fuente, no un umbral fisiológico de la especie.

**Referencias**

Chase, R. R. (2026). *Transpiration monitoring reveals diverse drought coping strategies in wild and cultivated enset (Ensete ventricosum)* [Conjunto de datos]. Zenodo. [doi:10.5281/zenodo.23213759](https://doi.org/10.5281/zenodo.23213759).

Lieth, H. *Tensiometer-based irrigation of potted plants*. University of California, Davis. [Informe](https://lieth.ucdavis.edu/research/tens/96/potirg.htm).

Kombala Liyanage, D., Chathuranga, I., Mori, B. A. y Thilakarathna, M. S. (2022). *A Simple, Semi-Automated, Gravimetric Method to Simulate Drought Stress on Plants*. Agronomy, 12(2), 349. [Artículo](https://doi.org/10.3390/agronomy12020349).
