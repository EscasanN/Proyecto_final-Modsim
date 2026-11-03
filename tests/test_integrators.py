import math

import pytest

from src.macetas.integrators import euler_step, rk4_step


@pytest.mark.parametrize("solver", [euler_step, rk4_step])
def test_constant_derivative_and_invalid_steps(solver):
    assert solver(lambda t, y: 2.0, 3.0, 5.0, 0.75) == pytest.approx(6.5)
    for step in (0, -1, math.nan, math.inf):
        with pytest.raises(ValueError):
            solver(lambda t, y: 1.0, 0, 0, step)


def test_rk4_evaluates_time_at_intermediate_stages():
    assert rk4_step(lambda t, y: t ** 3, 2.0, 0.0, 0.5) == pytest.approx((2.5 ** 4 - 2.0 ** 4) / 4)


@pytest.mark.parametrize("solver, minimum, maximum", [(euler_step, 1.9, 2.1), (rk4_step, 15, 17)])
def test_global_convergence_order(solver, minimum, maximum):
    errors = []
    for n in (16, 32):
        value = 1.0
        for i in range(n):
            value = solver(lambda t, y: y, i / n, value, 1 / n)
        errors.append(abs(value - math.e))
    assert minimum < errors[0] / errors[1] < maximum
