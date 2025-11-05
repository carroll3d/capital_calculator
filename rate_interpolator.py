from dataclasses import dataclass
from typing import Iterable, Tuple, Union
import numpy as np
from scipy.interpolate import PchipInterpolator

Number = Union[int, float]

@dataclass
class Curve:
    periods: np.ndarray
    rates: np.ndarray
    interpolator: PchipInterpolator

def make_curve(known_periods: Iterable[Number], known_rates: Iterable[Number]) -> Curve:
    x = np.asarray(list(known_periods), dtype=float).ravel()
    y = np.asarray(list(known_rates), dtype=float).ravel()
    if x.size != y.size or x.size < 2:
        raise ValueError("Provide at least two (period, rate) points with matching lengths.")
    order = np.argsort(x)
    x = x[order]; y = y[order]
    if np.nanmax(y) > 1.0:
        y = y / 100.0
    ux, inv = np.unique(x, return_inverse=True)
    if ux.shape[0] != x.shape[0]:
        sums = np.bincount(inv, weights=y)
        counts = np.bincount(inv)
        y = sums / counts; x = ux
    if np.any(np.diff(x) <= 0):
        raise ValueError("Periods must be strictly increasing after deduplication.")
    interp = PchipInterpolator(x, y, extrapolate=False)
    return Curve(periods=x, rates=y, interpolator=interp)

def interpolate(curve: Curve, query_periods: Iterable[Number]) -> Tuple[np.ndarray, np.ndarray]:
    qx = np.asarray(list(query_periods), dtype=float).ravel()
    qy = curve.interpolator(qx)
    lb, ub = curve.periods[0], curve.periods[-1]
    oob = (qx < lb) | (qx > ub)
    if np.any(oob):
        qy = qy.astype(float)
        qy[oob] = np.nan
    return qx, qy

def interpolate_range(curve: Curve, start: Number, end: Number, step: Number = 1) -> Tuple[np.ndarray, np.ndarray]:
    if step == 0:
        raise ValueError("step must be non-zero")
    if end < start and step > 0:
        step = -abs(step)
    qx = np.arange(start, end + (step if step > 0 else 0), step, dtype=float)
    return interpolate(curve, qx)
