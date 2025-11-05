from __future__ import annotations
from typing import List, Optional
import re, io, requests
import numpy as np
import pandas as pd
import pdfplumber

FHLB_CHICAGO_DAILY_PDF = "https://www.fhlbc.com/docs/default-source/daily-rates/dailypdf.pdf"

TERM_PAT = re.compile(r'(?P<num>\d+(?:\.\d+)?)\s*(?P<unit>years?|yrs?|y|months?|mos?|mo|m)', re.IGNORECASE)
PCT_PAT  = re.compile(r'(\d{1,2}\.\d{2,3})\s*%')

def _to_months(term_str: str) -> Optional[float]:
    m = TERM_PAT.search(term_str or "")
    if not m: return None
    num = float(m.group("num"))
    unit = m.group("unit").lower()
    return num * 12.0 if unit.startswith("y") else num

def _as_decimal(rate_str: str) -> Optional[float]:
    s = (rate_str or "").strip().replace("%", "")
    try:
        v = float(s); return v/100.0 if v > 1.0 else v
    except: return None

def fetch_pdf_bytes(url: str = FHLB_CHICAGO_DAILY_PDF) -> bytes:
    import requests
    resp = requests.get(url, timeout=20); resp.raise_for_status(); return resp.content

def parse_pdf_to_points(pdf_bytes: bytes) -> pd.DataFrame:
    lines: List[str] = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            for ln in text.splitlines():
                ln = ln.strip()
                if ln:
                    lines.append(ln)
    rows = []
    for ln in lines:
        tmatch = TERM_PAT.search(ln)
        if not tmatch: continue
        pmatch = PCT_PAT.search(ln)
        if not pmatch:
            toks = re.findall(r'\d+\.\d{2,3}', ln)
            if toks:
                rate_val = _as_decimal(toks[-1])
            else:
                continue
        else:
            rate_val = _as_decimal(pmatch.group(1))
        months = _to_months(tmatch.group(0))
        if months and rate_val is not None:
            rows.append((months, rate_val))
    if not rows:
        raise RuntimeError("Could not parse any (term, rate) pairs from PDF. Layout may have changed.")
    df = pd.DataFrame(rows, columns=["months", "rate_decimal"]).groupby("months", as_index=False)["rate_decimal"].mean().sort_values("months")
    df = df[(df["months"] > 0) & (df["months"] <= 360)]
    if df.empty:
        raise RuntimeError("Parsed PDF but no plausible tenor/rate pairs remained after filtering.")
    df["source"] = "chicago_pdf"
    return df

def fetch_chicago_daily_rates(url: str = FHLB_CHICAGO_DAILY_PDF) -> pd.DataFrame:
    pdf = fetch_pdf_bytes(url)
    df = parse_pdf_to_points(pdf)
    df["source"] = url or "chicago_pdf"
    return df
