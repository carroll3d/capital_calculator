# Amortization + IRB (10.5%) + Curves — M_used in months
- IRB capital uses **10.5%** of RWA.
- **Effective Maturity (M)**: Constant 2.5 or Calculated (Basel §109).
- **M_used column shows the monthly value** (computed years ÷ 12).
- Includes curve pages (Interpolator + FHLB Boston/Chicago).

## Run
```bash
pip install -r requirements.txt
streamlit run streamlit_app.py
```
© 2025
