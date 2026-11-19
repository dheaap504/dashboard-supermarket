"""Sumber data + kolom turunan.

DATA_SOURCE (secrets / env):
  - "parquet"  : data/supermarket.parquet (default, hasil scripts/prepare_data.py)
  - "supabase" : tabel Postgres Supabase via REST (untuk data yang terus bertambah)
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np
import pandas as pd
import requests
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
PARQUET = ROOT / "data" / "supermarket.parquet"
REPORT = ROOT / "data" / "quality_report.json"

DISC_BINS = [-0.1, 0, 5, 10, 20, 30, 50]
DISC_LABELS = ["0%", "1–5%", "6–10%", "11–20%", "21–30%", "31–50%"]
DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
DAYS_ID = {"Monday": "Senin", "Tuesday": "Selasa", "Wednesday": "Rabu", "Thursday": "Kamis",
           "Friday": "Jumat", "Saturday": "Sabtu", "Sunday": "Minggu"}
MONTHS_ID = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"]


def setting(key: str, default: str | None = None) -> str | None:
    try:
        if key in st.secrets:
            return str(st.secrets[key])
    except Exception:
        pass
    return os.environ.get(key, default)


def _from_supabase() -> pd.DataFrame:
    url = setting("SUPABASE_URL").rstrip("/")
    key = setting("SUPABASE_ANON_KEY")
    table = setting("SUPABASE_TABLE", "supermarket_sales")
    headers = {"apikey": key}
    if key.startswith("eyJ"):
        headers["Authorization"] = f"Bearer {key}"
    rows, step, start = [], 1000, 0
    while True:
        r = requests.get(f"{url}/rest/v1/{table}?select=*", timeout=60,
                         headers={**headers, "Range": f"{start}-{start + step - 1}"})
        r.raise_for_status()
        batch = r.json()
        rows.extend(batch)
        if len(batch) < step:
            break
        start += step
    return pd.DataFrame(rows)


def enrich(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["transaction_datetime"] = pd.to_datetime(df["transaction_datetime"])
    df["date"] = df["transaction_datetime"].dt.normalize()
    df["month"] = df["transaction_datetime"].dt.to_period("M").dt.to_timestamp()
    df["week"] = df["transaction_datetime"].dt.to_period("W").dt.start_time
    df["disc_bin"] = pd.cut(df["discount_percent"], DISC_BINS, labels=DISC_LABELS).astype(str)
    # diskon maksimum sebelum transaksi rugi (titik impas)
    df["break_even_disc"] = (1 - df["unit_cost"] / df["regular_price"]) * 100
    df["is_loss"] = df["gross_profit"] < 0
    df["discount_value"] = df["gross_sales"] - df["net_sales"]
    df["day_id"] = df["day_name"].astype(str).map(DAYS_ID)
    for c in df.select_dtypes(["object", "string"]).columns:
        if c not in ("transaction_id", "customer_id", "product_id", "product_name") and df[c].nunique() < 300:
            df[c] = df[c].astype("category")
    return df


@st.cache_data(ttl=int(setting("CACHE_TTL_SECONDS", "600")), show_spinner="Memuat data…")
def load_data() -> tuple[pd.DataFrame, str]:
    source = (setting("DATA_SOURCE", "parquet") or "parquet").lower()
    raw = _from_supabase() if source == "supabase" else pd.read_parquet(PARQUET)
    stamp = pd.Timestamp.now(tz="Asia/Jakarta").strftime("%d %b %Y %H:%M WIB")
    return enrich(raw), f"{source} · dimuat {stamp}"


@st.cache_data
def load_report() -> dict:
    return json.loads(REPORT.read_text())


def nf(v: float, d: int = 0, sign: bool = False) -> str:
    """Format angka gaya Indonesia: 1.234,5"""
    s = f"{v:+,.{d}f}" if sign else f"{v:,.{d}f}"
    s = s.replace(",", "_").replace(".", ",").replace("_", ".")
    zero = "0" if d == 0 else "0," + "0" * d
    return s.replace("-" + zero, zero).replace("+" + zero, zero)


def money(v: float, d: int = 0) -> str:
    """$ dengan singkatan rb/jt untuk angka besar."""
    a = abs(v)
    sign = "−" if v < 0 else ""
    if a >= 1e6:
        return f"{sign}${nf(a / 1e6, 2)} jt"
    if a >= 1e4:
        return f"{sign}${nf(a / 1e3, 1)} rb"
    return f"{sign}${nf(a, d)}"
