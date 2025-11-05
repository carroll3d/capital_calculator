from dataclasses import dataclass
from typing import Optional, Literal, Dict
import math
import numpy as np
from scipy.stats import norm

CAPITAL_RATE = 0.105  # 10.5%

ExposureType = Literal[
    "corporate - general",
    "corporate - project finance",
    "corporate - object finance",
    "corporate - commodities finance",
    "corporate - income producing RE",
    "corporate - HVCRE",
    "sovereign",
    "bank",
    "retail"
]

@dataclass
class IRBInputs:
    pd: float
    lgd: float
    ead: float
    m: Optional[float] = 2.5

@dataclass
class IRBOutputs:
    R: float
    b: float
    maturity_adj: float
    K: float
    rwa: float
    capital: float

def _clip_pd(pd: float) -> float:
    return float(np.clip(pd, 1e-10, 1 - 1e-10))

def _corporate_R(pd: float) -> float:
    pd = _clip_pd(pd)
    a = (1 - math.exp(-50.0 * pd)) / (1 - math.exp(-50.0))
    return 0.12 * a + 0.24 * (1 - a)

def _retail_other_R(pd: float) -> float:
    pd = _clip_pd(pd)
    a = (1 - math.exp(-35.0 * pd)) / (1 - math.exp(-35.0))
    return 0.03 * a + 0.16 * (1 - a)

def _maturity_b(pd: float) -> float:
    pd = _clip_pd(pd)
    return (0.11852 - 0.05478 * math.log(pd)) ** 2

def _K_uncapped(pd: float, lgd: float, R: float) -> float:
    pd = _clip_pd(pd)
    z_pd = norm.ppf(pd)
    z_999 = norm.ppf(0.999)
    root = math.sqrt(R / (1 - R))
    inner = (z_pd / math.sqrt(1 - R)) + root * z_999
    return lgd * (norm.cdf(inner) - pd)

def _apply_maturity(K: float, pd: float, m: Optional[float]):
    if m is None:
        return K, 0.0, 1.0
    b = _maturity_b(pd)
    ma = (1 + (m - 2.5) * b) / (1 - 1.5 * b)
    return K * ma, b, ma

def irb_capital(exposure_type, inputs: IRBInputs, bank_is_large_FI: bool = False) -> IRBOutputs:
    pd, lgd, ead, m = inputs.pd, inputs.lgd, inputs.ead, inputs.m
    pd = _clip_pd(pd)

    if exposure_type == "retail":
        R = _retail_other_R(pd)
        K = _K_uncapped(pd, lgd, R)
        b, ma = 0.0, 1.0
    else:
        if exposure_type == "corporate - HVCRE":
            a = (1 - math.exp(-50.0 * pd)) / (1 - math.exp(-50.0))
            R = 0.12 * a + 0.30 * (1 - a)
        else:
            R = _corporate_R(pd)
            if bank_is_large_FI and exposure_type == "bank":
                R *= 1.25
        K_base = _K_uncapped(pd, lgd, R)
        K, b, ma = _apply_maturity(K_base, pd, m)

    rwa = 12.5 * K * ead
    capital = CAPITAL_RATE * rwa
    return IRBOutputs(R=R, b=b, maturity_adj=ma, K=K, rwa=rwa, capital=capital)

def slotting_capital(ead: float, risk_weight_pct: float) -> Dict[str, float]:
    rw = max(0.0, float(risk_weight_pct)) / 100.0
    rwa = rw * ead
    return {"rwa": rwa, "capital": CAPITAL_RATE * rwa}
