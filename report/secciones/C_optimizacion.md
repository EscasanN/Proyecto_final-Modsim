# Técnica adicional e integración de la mejora

Texto de C para integrar en el informe colectivo. Evidencia ejecutada y cifras:
`results/optimization/synthetic/README.md`; detalle reproducible:
`docs/optimization.md`. Este texto no sustituye las secciones experimentales de D.

Se propone optimizar una política de riego por umbrales mediante enjambre de
partículas global (PSO). El método comparte experiencias individuales y del
enjambre [kennedy1995pso]. Su implementación con inercia y coeficientes de
atracción se contrastó con la documentación técnica [pyswarms_global_best].
La influencia de coeficientes sobre las trayectorias motiva comparar dos inercias,
sin suponer garantía de óptimo [innocente2010coefficients].

La solución representa activación, objetivo y dosis máxima, en mL. La primera
decide cuándo regar; la segunda define el déficit que se intenta alcanzar; la
tercera limita cada dosis. Los tres parámetros se obtienen de coordenadas en
[0,1], se llevan a una rejilla y se reparan de forma que el objetivo sea menor
que la activación y esta no exceda el límite operacional. Las dosis se redondean
hacia abajo a la resolución del instrumento. Las revisiones, el presupuesto
diario y la frecuencia son restricciones comunes fijadas antes de buscar.

La función objetivo es el agua media aplicada, incluyendo reposición final al
mismo déficit inicial. La comparación prioriza factibilidad, luego violación
normalizada y finalmente agua. Así, una política que usa menos agua pero supera
el límite no gana a una factible. Un módulo independiente comprueba restricciones
y conservación directamente en la trayectoria y eventos. La reposición exacta
hereda la convención de B: límite por dosis y diario, con excepción de horario,
frecuencia ordinaria y redondeo para el cierre contable.

PSO actualiza `v = w*v + c1*r1*(pbest-x) + c2*r2*(gbest-x)` y `x = x+v`.
Los números aleatorios son independientes por coordenada, la velocidad se
limita y las posiciones se recortan al cubo normalizado. Se detiene por un
presupuesto fijo que incluye la población inicial. Las dos variantes usan
`w=.7` o `.4`, `c1=c2=1.4` y velocidad máxima `.2`. La búsqueda aleatoria
usa el mismo espacio, banco de simulaciones y número de evaluaciones.

PSO no necesita gradientes y admite los saltos de la política; una técnica
gradiente puede resultar poco informativa en las mesetas del redondeo. Una
rejilla o búsqueda aleatoria sigue siendo una alternativa razonable en tres
dimensiones. Por ello la pertinencia de PSO se somete a comparación y no se
afirma superioridad solo por su complejidad. No garantiza óptimo global, depende
de semillas, puede estancarse y puede sobreajustarse al simulador.

Se conservaron los parámetros físicos de A y el simulador de B. Los candidatos
comparten realizaciones ambientales pregeneradas y un banco de selección distinto.
La selección exige factibilidad en ambos bancos y guarda la política efectiva
antes de cualquier evaluación final. Los números de semillas finales se reservan
para D sin generar sus trayectorias. La evidencia disponible es sintética y usa
30 corridas independientes por variante del optimizador; no equivale a 30
experimentos físicos ni a las 30 réplicas finales por condición.

El modelo puede reducir pérdidas al aumentar el déficit porque su coeficiente
lineal es negativo. Aunque el cierre evita fingir ahorro vaciando la reserva,
no demuestra que ese déficit sea adecuado para la planta. El límite operacional,
la correspondencia con mediciones reales y la sensibilidad deben respaldarse
antes de interpretar una mejora. No se atribuye a este módulo validación real.
