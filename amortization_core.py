from dataclasses import dataclass
from typing import List
from math import isclose

@dataclass
class AmortRow:
    period: int
    payment: float
    interest: float
    principal: float
    balance_end: float
    balloon_due: float = 0.0

def pmt(principal: float, annual_rate: float, amort_years: float, payments_per_year: int = 12) -> float:
    n = int(round(amort_years * payments_per_year))
    if n <= 0:
        raise ValueError("Amortization term must be > 0.")
    if isclose(annual_rate, 0.0, abs_tol=1e-15):
        return principal / n
    r = annual_rate / payments_per_year
    return principal * r / (1 - (1 + r) ** (-n))

def amortization_schedule(
    principal: float,
    annual_rate: float,
    amort_years: float,
    maturity_years: float,
    payments_per_year: int = 12,
    round_to_cents: bool = True
) -> List[AmortRow]:
    if principal <= 0:
        raise ValueError("Principal must be > 0.")
    if maturity_years <= 0:
        raise ValueError("Maturity term must be > 0.")
    r = annual_rate / payments_per_year
    pay = pmt(principal, annual_rate, amort_years, payments_per_year)
    periods_to_list = int(round(maturity_years * payments_per_year))
    schedule: List[AmortRow] = []
    bal = float(principal)
    for k in range(1, periods_to_list + 1):
        interest = bal * r
        principal_pay = pay - interest
        if principal_pay > bal:
            principal_pay = bal
            pay_effective = interest + principal_pay
        else:
            pay_effective = pay
        bal = bal - principal_pay
        if round_to_cents:
            interest = round(interest, 2)
            principal_pay = round(principal_pay, 2)
            pay_effective = round(pay_effective, 2)
            bal = round(bal, 2)
        schedule.append(AmortRow(
            period=k,
            payment=pay_effective,
            interest=interest,
            principal=principal_pay,
            balance_end=bal,
            balloon_due=0.0
        ))
        if bal <= 0.0:
            break
    if len(schedule) == periods_to_list and schedule[-1].balance_end > 0:
        last = schedule[-1]
        schedule[-1] = AmortRow(
            period=last.period,
            payment=last.payment,
            interest=last.interest,
            principal=last.principal,
            balance_end=last.balance_end,
            balloon_due=last.balance_end
        )
    return schedule
