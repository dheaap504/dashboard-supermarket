"""Agregasi, insight otomatis, dan simulasi. Margin = total laba / total penjualan bersih (tertimbang)."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .data import DISC_LABELS, money, nf


def kpis(df: pd.DataFrame) -> dict:
    rev, prof = df.net_sales.sum(), df.gross_profit.sum()
    return dict(
        revenue=rev, profit=prof, margin=prof / rev * 100 if rev else 0, tx=len(df),
        aov=df.net_sales.mean() if len(df) else 0, units=int(df.quantity.sum()),
        customers=df.customer_id.nunique(), discount=df.discount_value.sum(),
        gross=df.gross_sales.sum(), loss_rows=int(df.is_loss.sum()),
        loss_sum=df.loc[df.is_loss, "gross_profit"].sum(),
    )


def agg(df: pd.DataFrame, by, sort: str | None = "revenue") -> pd.DataFrame:
    g = df.groupby(by, observed=True).agg(
        rows=("transaction_id", "size"), revenue=("net_sales", "sum"), profit=("gross_profit", "sum"),
        units=("quantity", "sum"), qty=("quantity", "mean"), aov=("net_sales", "mean"),
        discount=("discount_value", "sum"), disc_pct=("discount_percent", "mean"),
        loss_rows=("is_loss", "sum"),
    )
    g["margin"] = g.profit / g.revenue * 100
    g["share"] = g.revenue / g.revenue.sum() * 100
    g["loss_rate"] = g.loss_rows / g.rows * 100
    g = g.reset_index()
    return g.sort_values(sort, ascending=False) if sort else g


def by_period(df: pd.DataFrame, freq: str = "month") -> pd.DataFrame:
    g = agg(df, freq, sort=None).sort_values(freq)
    return g


def discount_table(df: pd.DataFrame) -> pd.DataFrame:
    g = agg(df, "disc_bin", sort=None)
    g["disc_bin"] = pd.Categorical(g.disc_bin, DISC_LABELS, ordered=True)
    return g.sort_values("disc_bin")


def category_breakeven(df: pd.DataFrame) -> pd.DataFrame:
    g = df.groupby("product_category", observed=True).agg(
        rows=("transaction_id", "size"), revenue=("net_sales", "sum"), profit=("gross_profit", "sum"),
        break_even=("break_even_disc", "median"), disc=("discount_percent", "mean"),
        beyond=("is_loss", "mean"), loss=("gross_profit", lambda s: s[s < 0].sum()),
    ).reset_index()
    g["margin"] = g.profit / g.revenue * 100
    g["beyond"] *= 100
    return g.sort_values("loss")


def discount_cap(df: pd.DataFrame, cap: float) -> dict:
    """Perkiraan laba bila diskon dibatasi maksimal `cap`%. Asumsi: volume tidak berubah
    (didukung data: jumlah per transaksi tidak naik seiring diskon)."""
    d = np.minimum(df.discount_percent.values, cap)
    new_price = df.regular_price.values * (1 - d / 100)
    new_rev = (df.quantity.values * new_price).sum()
    new_profit = (df.quantity.values * (new_price - df.unit_cost.values)).sum()
    cur_profit, cur_rev = df.gross_profit.sum(), df.net_sales.sum()
    affected = (df.discount_percent > cap)
    return dict(cap=cap, profit_now=cur_profit, profit_new=new_profit, gain=new_profit - cur_profit,
                rev_now=cur_rev, rev_new=new_rev, margin_now=cur_profit / cur_rev * 100,
                margin_new=new_profit / new_rev * 100, affected=int(affected.sum()),
                affected_pct=affected.mean() * 100,
                loss_rows_new=int(((df.quantity.values * (new_price - df.unit_cost.values)) < 0).sum()))


def pareto(df: pd.DataFrame, key: str) -> pd.DataFrame:
    s = df.groupby(key, observed=True).net_sales.sum().sort_values(ascending=False)
    out = pd.DataFrame({"share_items": np.arange(1, len(s) + 1) / len(s) * 100,
                        "share_rev": s.cumsum().values / s.sum() * 100})
    return out


def top_share(df: pd.DataFrame, key: str, frac: float = 0.2) -> float:
    s = df.groupby(key, observed=True).net_sales.sum().sort_values(ascending=False)
    return s.head(max(1, int(len(s) * frac))).sum() / s.sum() * 100 if len(s) else 0


def customer_freq(df: pd.DataFrame) -> pd.DataFrame:
    c = df.groupby("customer_id").agg(tx=("transaction_id", "size"), spend=("net_sales", "sum"))
    c["freq"] = np.where(c.tx >= 5, "5+", c.tx.astype(str))
    g = c.groupby("freq").agg(customers=("tx", "size"), spend=("spend", "sum"), avg=("spend", "mean")).reset_index()
    g["share_c"] = g.customers / g.customers.sum() * 100
    g["share_rev"] = g.spend / g.spend.sum() * 100
    order = ["1", "2", "3", "4", "5+"]
    g["freq"] = pd.Categorical(g.freq, order, ordered=True)
    return g.sort_values("freq")


def heat_day_hour(df: pd.DataFrame) -> pd.DataFrame:
    return df.pivot_table(index="day_name", columns="shopping_hour", values="transaction_id",
                          aggfunc="size", observed=True).fillna(0)


def supplier_table(df: pd.DataFrame) -> pd.DataFrame:
    g = df.groupby("supplier_id", observed=True).agg(
        supplier_type=("supplier_type", "first"), region=("supplier_region", "first"),
        rating=("supplier_rating", "first"), ontime=("supplier_on_time_delivery_rate", "mean"),
        defect=("supplier_defect_rate", "mean"), lead=("supplier_lead_time_days", "mean"),
        delay=("delivery_delay_days", "mean"), revenue=("net_sales", "sum"), rows=("transaction_id", "size"),
        delayed=("delivery_status", lambda s: (s.astype(str).isin(["Delayed", "Cancelled"])).mean() * 100),
    ).reset_index()
    # skor gabungan sederhana 0–100: tepat waktu tinggi, cacat & lead time rendah
    def z(s):
        return (s - s.min()) / (s.max() - s.min() + 1e-9)
    g["score"] = (0.45 * z(g.ontime) + 0.35 * (1 - z(g.defect)) + 0.20 * (1 - z(g.lead))) * 100
    return g.sort_values("score", ascending=False)


def store_table(df: pd.DataFrame) -> pd.DataFrame:
    g = df.groupby("store_id", observed=True).agg(
        store_type=("store_type", "first"), region=("store_region", "first"), city=("store_city", "first"),
        size=("store_size_sqft", "first"), rating=("store_rating", "first"),
        revenue=("net_sales", "sum"), profit=("gross_profit", "sum"), rows=("transaction_id", "size"),
        customers=("customer_id", "nunique"),
    ).reset_index()
    g["margin"] = g.profit / g.revenue * 100
    g["rank"] = g.revenue.rank(ascending=False).astype(int)
    return g.sort_values("revenue", ascending=False)


def insights(df: pd.DataFrame) -> list[str]:
    k = kpis(df)
    dt = discount_table(df)
    out = []
    if len(dt) >= 2:
        a, b = dt.iloc[0], dt.iloc[-1]
        out.append(f"Margin turun dari **{nf(a.margin, 1)}%** (tanpa diskon) ke **{nf(b.margin, 1)}%** pada diskon "
                   f"{b.disc_bin}, sementara jumlah barang per transaksi tetap ~{nf(dt.qty.mean(), 1)}.")
    out.append(f"**{nf(k['loss_rows'] / max(k['tx'], 1) * 100, 1)}%** baris transaksi rugi (total "
               f"{money(k['loss_sum'])}) — semuanya karena diskon melewati titik impas.")
    cat = agg(df, "product_category")
    if len(cat):
        hi, lo = cat.loc[cat.margin.idxmax()], cat.loc[cat.margin.idxmin()]
        out.append(f"Margin kategori berkisar **{nf(lo.margin, 1)}%** ({lo.product_category}) hingga "
                   f"**{nf(hi.margin, 1)}%** ({hi.product_category}).")
    out.append(f"20% produk teratas menyumbang **{nf(top_share(df, 'product_id'), 0)}%** penjualan; "
               f"20% pelanggan teratas **{nf(top_share(df, 'customer_id'), 0)}%**.")
    cf = customer_freq(df)
    one = cf.loc[cf.freq == "1", "share_c"]
    if len(one):
        out.append(f"**{nf(one.iloc[0], 0)}%** pelanggan hanya bertransaksi sekali dalam periode ini.")
    peak = df.shopping_hour.between(7, 10).mean() * 100
    out.append(f"**{nf(peak, 0)}%** transaksi terjadi pukul 07.00–10.59.")
    return out
