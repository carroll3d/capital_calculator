import streamlit as st
import numpy as np
import pandas as pd
from dataclasses import asdict

from amortization_core import amortization_schedule, pmt
from basel_irb import IRBInputs, irb_capital, slotting_capital, CAPITAL_RATE

st.set_page_config(page_title="Loan Tools: Amortization + IRB (10.5%) + Curves", page_icon="💸", layout="wide")
st.title("💸 Amortization Table + Basel IRB (10.5%) + Curves")

with st.sidebar:
    st.header("Loan Inputs")
    colA, colB = st.columns(2)
    with colA:
        principal = st.number_input("Principal", value=200_000.00, step=1000.0, min_value=0.0, format="%.2f")
        rate_pct = st.number_input("Annual Interest Rate (%)", value=5.40, step=0.01, min_value=0.0, format="%.2f")
    with colB:
        amort_months = st.number_input("Amortization (months)", value=240, step=1, min_value=1)
        maturity_months = st.number_input("Maturity (months)", value=60, step=1, min_value=1)

    payments_per_year = st.selectbox("Payments per year", options=[12, 24, 26, 52], index=0)
    round_to_cents = st.checkbox("Round to cents", value=True)

st.sidebar.markdown('---')
st.sidebar.markdown('Pages: **Rate Interpolator** and **FHLB → Curve** (left sidebar)')

amort_years = amort_months / 12
maturity_years = maturity_months / 12
annual_rate = rate_pct / 100.0

pay = pmt(principal, annual_rate, amort_years, payments_per_year)
schedule = amortization_schedule(
    principal=principal,
    annual_rate=annual_rate,
    amort_years=amort_years,
    maturity_years=maturity_years,
    payments_per_year=payments_per_year,
    round_to_cents=round_to_cents
)
df = pd.DataFrame([asdict(r) for r in schedule]).set_index("period")

c1, c2, c3, c4 = st.columns(4)
c1.metric("Payment", f"${pay:,.2f}")
total_interest = df["interest"].sum()
c2.metric("Interest to Maturity", f"${total_interest:,.2f}")
balloon = df["balloon_due"].iloc[-1] if "balloon_due" in df.columns else 0.0
c3.metric("Balloon at Maturity", f"${balloon:,.2f}")
c4.metric("Periods Listed", f"{len(df):,}")

# ---- Basel IRB (10.5%) per period ----
st.markdown("## Basel III IRB Capital (per period, 10.5%)")
exposure_type = st.selectbox(
    "Exposure type (Basel asset class)",
    [
        "corporate - general",
        "corporate - project finance",
        "corporate - object finance",
        "corporate - commodities finance",
        "corporate - income producing RE",
        "corporate - HVCRE",
        "sovereign",
        "bank",
        "retail",
    ],
    index=0,
)

colA, colB, colC, colD = st.columns(4)
with colA:
    pd_pct = st.number_input("PD (%)", value=1.00, min_value=0.0001, step=0.01)
with colB:
    lgd_pct = st.number_input("LGD (%)", value=45.0, min_value=0.0, max_value=100.0, step=1.0)
with colC:
    m_choice = st.selectbox("Effective Maturity (M) method", ["Constant 2.5", "Calculated (Basel §109)"], index=0,
                            help="Calculated uses weighted-average time of cash flows (principal + interest).")
with colD:
    ead_source = st.selectbox("EAD source", ["Use period-end balance", "Custom constant"], index=0)

# Compute M if calculated: M = sum(t * CF_t) / sum(CF_t); CF_t = principal + interest; t in years
if m_choice.startswith("Calculated"):
    periods = df.index.values.astype(float)
    t_years = periods / float(payments_per_year)
    cf = (df["principal"].values + df["interest"].values).astype(float)
    denom = np.sum(cf)
    M_eff_years = float(np.sum(t_years * cf) / denom) if denom > 0 else 2.5
    M_eff_years = max(1.0, min(5.0, M_eff_years))
else:
    M_eff_years = 2.5

# Store monthly value in M_used (divide years by 12 per user request)
M_used_monthly = M_eff_years / 12.0

custom_ead = None
if ead_source == "Custom constant":
    custom_ead = st.number_input("Custom EAD (applies to all periods)", value=float(principal), min_value=0.0, step=1000.0)

use_slotting = exposure_type in (
    "corporate - project finance",
    "corporate - object finance",
    "corporate - commodities finance",
    "corporate - income producing RE",
    "corporate - HVCRE",
) and st.checkbox("Use supervisory slotting (enter risk weight %)", value=False)

slotting_rw = None
if use_slotting:
    slotting_rw = st.number_input("Slotting risk weight (%)", value=115.0, min_value=0.0, step=5.0)

pd_dec = pd_pct / 100.0
lgd_dec = lgd_pct / 100.0

for c in ["irb_R","irb_b","irb_MA","K_perEAD","RWA","IRB capital","M_used"]:
    df[c] = np.nan

for idx, row in df.iterrows():
    ead_val = float(row["balance_end"]) if ead_source == "Use period-end balance" else float(custom_ead or 0.0)
    if ead_val <= 0:
        df.loc[idx, ["irb_R","irb_b","irb_MA","K_perEAD","RWA","IRB capital","M_used"]] = [0,0,1,0,0,0,M_used_monthly]
        continue

    if use_slotting:
        out = slotting_capital(ead=ead_val, risk_weight_pct=slotting_rw or 0.0)
        df.loc[idx, ["irb_R","irb_b","irb_MA","K_perEAD","RWA","IRB capital","M_used"]] = [np.nan,0,1,0,out["rwa"],out["capital"],M_used_monthly]
    else:
        inputs = IRBInputs(pd=pd_dec, lgd=lgd_dec, ead=ead_val, m=M_eff_years if exposure_type != "retail" else None)
        res = irb_capital(exposure_type, inputs)
        df.loc[idx, ["irb_R","irb_b","irb_MA","K_perEAD","RWA","IRB capital","M_used"]] = [res.R, res.b, res.maturity_adj, res.K, res.rwa, res.capital, M_used_monthly]

st.markdown(f"### Amortization Table (with RWA and IRB capital @ {int(CAPITAL_RATE*1000)/10:.1f}%)")
st.caption("Note: M_used is now the monthly value (years/12).")
st.dataframe(df[["payment","interest","principal","balance_end","balloon_due","M_used","RWA","IRB capital"]],
             use_container_width=True, height=520)

st.markdown("### IRB Capital Time Series")
st.line_chart(df["IRB capital"])

csv = df.reset_index().to_csv(index=False).encode("utf-8")
st.download_button("Download Full Table (CSV)", data=csv, file_name="amortization_with_RWA_IRB_capital_Mmonthly.csv", mime="text/csv")
