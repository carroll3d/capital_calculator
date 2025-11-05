from typing import List, Optional
import re
import pandas as pd
import numpy as np

FHLB_BOSTON_RATES_URL = "https://www.fhlbboston.com/rates/"

TERM_PATTERN = re.compile(
    r'(?P<num>\d+(?:\.\d+)?)\s*(?P<Unit>years?|yrs?|y|months?|mos?|mo|m|weeks?|wks?|wk|w|days?|d)',
    re.IGNORECASE
)

UNIT_TO_MONTHS = {
    'y': 12, 'yr': 12, 'yrs': 12, 'year': 12, 'years': 12,
    'm': 1, 'mo': 1, 'mos': 1, 'month': 1, 'months': 1,
    'w': 12/52, 'wk': 12/52, 'wks': 12/52, 'week': 12/52, 'weeks': 12/52,
    'd': 12/365, 'day': 12/365, 'days': 12/365,
}

def _term_to_months(term: str) -> Optional[float]:
    if term is None:
        return None
    s = str(term).strip()
    if not s:
        return None
    m = TERM_PATTERN.search(s)
    if not m:
        compact = re.match(r'(?P<num>\d+(?:\.\d+)?)(?P<Unit>[YyMmWwDd])$', s)
        if compact:
            num = float(compact.group('num'))
            unit = compact.group('Unit').lower()
            mult = {'y':12, 'm':1, 'w':12/52, 'd':12/365}[unit]
            return num * mult
        return None
    num = float(m.group('num'))
    unit = m.group('Unit').lower()
    unit_key = {'yr':'yr','yrs':'yrs','y':'y',
                'mo':'mo','mos':'mos','m':'m',
                'wk':'wk','wks':'wks','w':'w',
                'd':'d','day':'d','days':'d',
                'year':'y','years':'y','month':'m','months':'m','week':'w','weeks':'w'}.get(unit, unit)
    mult = UNIT_TO_MONTHS.get(unit_key)
    if mult is None:
        return None
    return num * mult

def _detect_rate_col(cols: List[str]) -> Optional[str]:
    lowered = [c.lower() for c in cols]
    for cand in ['rate', 'rates', 'coupon', 'yield', 'all-in', 'today']:
        for col, low in zip(cols, lowered):
            if cand in low:
                return col
    return None

def _detect_term_col(cols: List[str]) -> Optional[str]:
    lowered = [c.lower() for c in cols]
    for col, low in zip(cols, lowered):
        if any(k in low for k in ['term', 'maturity', 'tenor', 'period']):
            return col
    return None

def fetch_fhlb_boston_rates(url: str = FHLB_BOSTON_RATES_URL) -> pd.DataFrame:
    try:
        tables = pd.read_html(url)
    except Exception as e:
        raise RuntimeError(f"Unable to read any tables from {url}: {e}")
    rows = []
    for t in tables:
        if t.empty:
            continue
        cols = list(t.columns)
        term_col = _detect_term_col(cols)
        rate_col = _detect_rate_col(cols)
        if term_col is None or rate_col is None:
            num_like = [c for c in cols if pd.api.types.is_numeric_dtype(t[c])]
            txt_like = [c for c in cols if not pd.api.types.is_numeric_dtype(t[c])]
            if len(num_like) == 1 and len(txt_like) == 1:
                rate_col, term_col = num_like[0], txt_like[0]
            else:
                continue
        df = t[[term_col, rate_col]].copy()
        df.columns = ['term','rate_raw']
        def to_decimal(x):
            s = str(x).strip()
            if s.endswith('%'):
                try: return float(s.strip('%'))/100.0
                except: return np.nan
            try:
                v = float(s.replace(',',''))
                return v/100.0 if v > 1.0 else v
            except:
                return np.nan
        df['rate_decimal'] = df['rate_raw'].apply(to_decimal)
        df['months'] = df['term'].apply(_term_to_months)
        df = df.dropna(subset=['months','rate_decimal'])
        if not df.empty:
            df['source'] = url
            rows.append(df[['months','rate_decimal','source']])
    if not rows:
        raise RuntimeError("No usable public rates table found on the page. Rates may require member login.")
    out = pd.concat(rows, ignore_index=True)
    out = out.groupby('months', as_index=False)['rate_decimal'].mean().assign(source=url)
    out = out[out['months'] > 0].sort_values('months').reset_index(drop=True)
    return out
