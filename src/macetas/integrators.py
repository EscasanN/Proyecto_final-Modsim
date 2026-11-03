from __future__ import annotations

from collections.abc import Callable
from math import isfinite


def euler_step(rhs: Callable[[float, float], float], t: float, y: float, h: float) -> float:
    if not isfinite(h) or h <= 0:
        raise ValueError("El paso debe ser finito y positivo.")
    return y + h * rhs(t, y)


def rk4_step(rhs: Callable[[float, float], float], t: float, y: float, h: float) -> float:
    if not isfinite(h) or h <= 0:
        raise ValueError("El paso debe ser finito y positivo.")
    k1 = rhs(t, y)
    k2 = rhs(t + h / 2, y + h * k1 / 2)
    k3 = rhs(t + h / 2, y + h * k2 / 2)
    k4 = rhs(t + h, y + h * k3)
    return y + h * (k1 + 2 * k2 + 2 * k3 + k4) / 6


METHODS = {"euler": euler_step, "rk4": rk4_step}
