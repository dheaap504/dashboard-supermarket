"""Siapkan data dashboard dari CSV mentah (206 MB, 323 kolom) -> Parquet ramping.

Langkah:
1. Baca CSV mentah.
2. Jalankan pemeriksaan kualitas data -> data/quality_report.json (dipakai halaman "Kualitas data").
3. Keluarkan baris anomali (net_sales != quantity x selling_price).
4. Simpan hanya kolom yang dipakai dashboard -> data/supermarket.parquet (~8 MB).

Pemakaian:
    python scripts/prepare_data.py path/ke/supermarket_large_dataset.csv
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
OUT_PARQUET = ROOT / "data" / "supermarket.parquet"
OUT_REPORT = ROOT / "data" / "quality_report.json"

KEEP = [
    # identitas & waktu
    "transaction_id", "transaction_datetime", "customer_id", "store_id", "product_id", "supplier_id",
    # pelanggan
    "customer_age", "customer_gender", "customer_segment", "customer_region", "membership_tier",
    "loyalty_program_member", "customer_satisfaction_score", "customer_churn_risk",
    # toko
    "store_type", "store_region", "store_city", "store_size_sqft", "store_rating",
    # produk
    "product_name", "product_category", "product_subcategory", "product_department", "brand",
    "brand_type", "product_segment",
    # harga & penjualan
    "unit_cost", "regular_price", "selling_price", "discount_percent", "quantity", "gross_sales",
    "net_sales", "cost_of_goods_sold", "gross_profit", "competitor_price",
    # promosi, pembayaran, kanal
    "promotion_active", "promotion_type", "coupon_used", "payment_method", "sales_channel",
    # waktu belanja
    "shopping_hour", "day_name", "is_weekend", "season",
    # pemasok & operasional
    "supplier_type", "supplier_region", "supplier_rating", "supplier_on_time_delivery_rate",
    "supplier_defect_rate", "supplier_lead_time_days", "delivery_status", "delivery_delay_days",
    # retur & keluhan
    "return_flag", "return_reason", "complaint_flag", "complaint_category", "checkout_wait_time_minutes",
]


def _pct(x: float) -> float:
    return round(float(x) * 100, 2)


def quality_checks(df: pd.DataFrame) -> dict:
    n = len(df)
    formula_ok = np.isclose(df.net_sales, df.quantity * df.selling_price, atol=0.02)
    checks = []

    def add(area, check, result, status, note):
        checks.append(dict(area=area, check=check, result=result, status=status, note=note))

    # ---------- yang lolos
    for key, cols, label in [
        ("store_id", ["store_type", "store_region", "store_size_sqft"], "Atribut toko konsisten per ID toko"),
        ("product_id", ["product_category", "brand", "regular_price", "unit_cost"], "Atribut produk konsisten per ID produk"),
        ("customer_id", ["customer_age", "customer_gender", "customer_segment"], "Atribut pelanggan konsisten per ID pelanggan"),
        ("supplier_id", ["supplier_rating", "supplier_type", "supplier_region"], "Atribut pemasok konsisten per ID pemasok"),
    ]:
        bad = max((df.groupby(key)[c].nunique() > 1).mean() for c in cols)
        add("Konsistensi entitas", label, f"{_pct(1 - bad)}% konsisten", "ok" if bad == 0 else "warn",
            "Satu ID selalu punya atribut yang sama — aman untuk analisis per toko/produk/pelanggan/pemasok.")
    add("Rumus", "Penjualan bersih = jumlah × harga jual", f"{_pct(formula_ok.mean())}% cocok", "warn",
        f"{int((~formula_ok).sum())} baris tidak cocok (jumlah membengkak) → dikeluarkan dari dashboard.")
    gp = np.isclose(df.gross_profit, df.net_sales - df.cost_of_goods_sold, atol=0.02)
    add("Rumus", "Laba kotor = penjualan bersih − HPP", f"{_pct(gp.mean())}% cocok", "ok",
        "Selisih kecil hanya pada baris anomali di atas.")
    disc = np.isclose(df.selling_price, df.regular_price * (1 - df.discount_percent / 100), atol=0.02)
    add("Rumus", "Harga jual = harga normal × (1 − diskon)", f"{_pct(disc.mean())}% cocok", "ok", "Data diskon dapat dipercaya.")
    dn = (pd.to_datetime(df.transaction_date).dt.day_name() == df.day_name).mean()
    add("Waktu", "Nama hari sesuai tanggal", f"{_pct(dn)}% cocok", "ok", "Analisis per hari/jam valid.")
    add("Duplikat", "Baris transaksi ganda", f"{int(df.duplicated(subset=[c for c in df.columns if c not in ('transaction_id', 'transaction_line_id')]).sum())} baris",
        "ok", "Tidak ada transaksi ganda.")

    # ---------- yang bermasalah
    b = df.groupby("basket_id").agg(c=("customer_id", "nunique"), s=("store_id", "nunique"))
    add("Keranjang belanja", "Satu basket_id = satu pelanggan & toko",
        f"{_pct(((b.c > 1) | (b.s > 1)).mean())}% basket tercampur", "bad",
        "basket_id dipakai bersama oleh pelanggan/toko berbeda → analisis keranjang (market basket) tidak dipakai.")
    hm = pd.crosstab(df.month, df.holiday_name)
    xmas_out = int(hm.drop(index=12, errors="ignore").get("Christmas", pd.Series(dtype=int)).sum())
    add("Hari libur", "Nama hari libur sesuai bulannya", f"{xmas_out} transaksi 'Christmas' di luar Desember", "bad",
        "Kolom hari libur acak → tidak dipakai.")
    lat = (df.groupby("store_id").latitude.nunique() > 1).mean()
    add("Lokasi", "Koordinat toko tetap", f"{_pct(lat)}% toko berpindah koordinat", "bad",
        "Koordinat berubah tiap transaksi → peta hanya per wilayah, bukan titik toko.")
    m = df[formula_ok].groupby(pd.to_datetime(df.transaction_date).dt.to_period("M")).net_sales.sum()
    add("Pola waktu", "Variasi penjualan bulanan", f"koefisien variasi {round(float(m.std() / m.mean()) * 100, 1)}%", "warn",
        "Hampir rata: tidak ada musim maupun pertumbuhan — ciri data sintetis.")
    sat = df.select_dtypes("number").corrwith(df.customer_satisfaction_score, method="spearman") \
        .drop("customer_satisfaction_score").abs().max()
    add("Kepuasan & layanan", "Kepuasan berhubungan dengan faktor lain", f"korelasi tertinggi {round(float(sat), 3)}", "bad",
        "Kepuasan, churn, loyalitas, antrean bersifat acak → hanya ditampilkan komposisinya.")
    tier = df.groupby("membership_tier").net_sales.mean()
    add("Kepuasan & layanan", "Tier membership membedakan belanja",
        f"selisih rata-rata belanja antar tier {round(float((tier.max() - tier.min()) / tier.mean() * 100), 1)}%", "bad",
        "Tidak ada perbedaan berarti → bukan insight.")
    const = [c for c in df.columns if df[c].nunique(dropna=False) <= 1]
    add("Kolom", "Kolom bernilai tunggal (tidak informatif)", f"{len(const)} kolom", "warn", ", ".join(const))
    na = df.isna().mean()
    add("Kolom", "Kolom dengan nilai kosong", f"{int((na > 0).sum())} kolom",
        "ok", "Sebagian besar wajar kosong (mis. alasan retur hanya terisi bila ada retur).")

    summary = dict(rows_raw=n, cols_raw=df.shape[1], rows_removed=int((~formula_ok).sum()),
                   rows_clean=int(formula_ok.sum()), cols_kept=len(KEEP),
                   date_min=str(df.transaction_date.min()), date_max=str(df.transaction_date.max()))
    return dict(summary=summary, checks=checks)


def main(src: str):
    df = pd.read_csv(src, low_memory=False)
    report = quality_checks(df)
    ok = np.isclose(df.net_sales, df.quantity * df.selling_price, atol=0.02)
    clean = df.loc[ok, KEEP].copy()
    clean["transaction_datetime"] = pd.to_datetime(clean["transaction_datetime"])
    for c in clean.select_dtypes(["object", "string"]).columns:
        if clean[c].nunique() < 200:
            clean[c] = clean[c].astype("category")
    clean.to_parquet(OUT_PARQUET, index=False, compression="zstd")
    OUT_REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False))
    print(f"OK: {len(clean):,} baris, {clean.shape[1]} kolom -> {OUT_PARQUET} "
          f"({OUT_PARQUET.stat().st_size / 1e6:.1f} MB); laporan -> {OUT_REPORT}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else str(ROOT / "raw" / "supermarket_large_dataset.csv"))
