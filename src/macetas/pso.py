"""PSO global en coordenadas normalizadas; ecuaciones citadas en docs/optimization.md."""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

import numpy as np


@dataclass(frozen=True)
class Score:
    water_ml: float
    violation: float = 0.0

    def __post_init__(self):
        if not all(isfinite(x) and x >= 0 for x in (self.water_ml, self.violation)):
            raise ValueError("Objetivo y violación deben ser finitos y no negativos.")

    @property
    def key(self):
        return (self.violation > 0, self.violation, self.water_ml)


@dataclass
class SearchResult:
    position: np.ndarray
    score: Score
    history: list[dict]
    evaluations: int


def search(objective, *, seed: int, particles: int = 20, iterations: int = 50,
           w: float = 0.7, c1: float = 1.4, c2: float = 1.4,
           velocity_max: float = 0.2, dimensions: int = 3,
           algorithm: str = "pso") -> SearchResult:
    """Exactamente particles*iterations llamadas; iteración 0 incluye inicialización.

    Menor Score.key gana: factible, violación, agua. La búsqueda aleatoria usa
    el mismo presupuesto y representación; no se reinicia el RNG por candidato.
    """
    if any(type(n) is not int or n < 1 for n in (particles, iterations, dimensions)):
        raise ValueError("Partículas, iteraciones y dimensiones deben ser enteros positivos.")
    if algorithm not in ("pso", "random"):
        raise ValueError("Algoritmo desconocido.")
    if not all(isfinite(v) and v >= 0 for v in (w, c1, c2, velocity_max)) or velocity_max == 0:
        raise ValueError("Coeficientes no negativos y velocidad máxima positiva requeridos.")
    rng = np.random.default_rng(seed)
    x = rng.random((particles, dimensions))
    v = np.zeros_like(x)
    personal = x.copy()
    scores = [None] * particles
    best_score, best = None, None
    history = []
    for iteration in range(iterations):
        for i in range(particles):
            score = objective(x[i].copy())
            if scores[i] is None or score.key < scores[i].key:
                scores[i], personal[i] = score, x[i].copy()
            if best_score is None or score.key < best_score.key:
                best_score, best = score, x[i].copy()
        history.append({"iteration": iteration, "evaluations": (iteration + 1) * particles,
                        "water_ml": best_score.water_ml, "violation": best_score.violation,
                        **{f"z{j}": float(value) for j, value in enumerate(best)}})
        if iteration + 1 == iterations:
            break
        if algorithm == "random":
            x = rng.random(x.shape)
        else:
            r1, r2 = rng.random(x.shape), rng.random(x.shape)
            v = np.clip(w * v + c1 * r1 * (personal - x) + c2 * r2 * (best - x),
                        -velocity_max, velocity_max)
            proposed = x + v
            v[(proposed < 0) | (proposed > 1)] = 0.0
            x = np.clip(proposed, 0, 1)
    return SearchResult(best, best_score, history, particles * iterations)
