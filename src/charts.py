"""Grafik Plotly bergaya Venus.

Aturan: setiap sumbu berjudul + satuan; label tidak menimpa data; garis referensi diberi label di
luar area data; `customdata` membawa kunci klik -> pop-up detail; batang ber-"track" abu muda.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from .data import DAYS, DAYS_ID, MONTHS_ID, nf

PURPLE = "#4318FF"
PURPLE_L = "#868CFF"
PURPLE_XL = "#C9CCFF"
NAVY = "#1B2559"
NAVY2 = "#2B3674"
MUTED = "#A3AED0"
MUTED2 = "#707EAE"
TRACK = "#E9EDF7"
GRID = "#EEF1F8"
GREEN = "#05CD99"
RED = "#EE5D50"
SEQ = [[0, "#F4F7FE"], [0.25, "#C9CCFF"], [0.6, "#868CFF"], [1, "#2C0FB3"]]
FONT = "DM Sans, -apple-system, Segoe UI, sans-serif"

CONFIG = {"displayModeBar": "hover", "displaylogo": False, "responsive": True,
          "modeBarButtons": [["toImage"]], "scrollZoom": False,
          "toImageButtonOptions": {"format": "png", "scale": 2, "filename": "grafik-supermarket"}}


def _base(fig: go.Figure, height: int = 320, legend: bool = False) -> go.Figure:
    fig.update_layout(
        height=height, autosize=True, margin=dict(l=8, r=16, t=16 if not legend else 40, b=8),
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        font=dict(family=FONT, size=12, color=MUTED2), separators=",.",
        hoverlabel=dict(bgcolor="white", bordercolor=TRACK, font=dict(family=FONT, size=12, color=NAVY)),
        showlegend=legend, clickmode="event+select", dragmode=False, bargap=0.35,
        legend=dict(orientation="h", y=1.02, yanchor="bottom", x=0, font=dict(size=12, color=NAVY2)),
    )
    fig.update_xaxes(showgrid=False, linecolor=TRACK, ticks="", automargin=True, fixedrange=True,
                     tickfont=dict(color=MUTED, size=11), title_font=dict(size=12, color=MUTED2), title_standoff=14)
    fig.update_yaxes(gridcolor=GRID, zeroline=False, automargin=True, fixedrange=True, griddash="dot",
                     tickfont=dict(color=MUTED, size=11), title_font=dict(size=12, color=MUTED2), title_standoff=14)
    return fig


def _month_label(ts) -> str:
    return f"{MONTHS_ID[ts.month - 1]} {str(ts.year)[2:]}"


# ================================================================== tren penjualan & laba
def trend(g: pd.DataFrame, freq: str) -> go.Figure:
    x = [(_month_label(t) if freq == "month" else t.strftime("%d/%m/%y")) for t in g[freq]]
    key = [t.strftime("%Y-%m-%d") for t in g[freq]]
    cd = np.stack([key, g.margin, g.rows], axis=1)
    fig = go.Figure()
    fig.add_trace(go.Bar(x=x, y=g.revenue, name="Penjualan bersih", marker=dict(color=PURPLE_XL, cornerradius=6),
                         customdata=cd, hovertemplate="<b>%{x}</b><br>Penjualan $%{y:,.0f}<br>"
                         "Margin %{customdata[1]:.1f}% · %{customdata[2]} transaksi<extra>klik untuk detail</extra>",
                         unselected=dict(marker=dict(opacity=0.4))))
    fig.add_trace(go.Bar(x=x, y=g.profit, name="Laba kotor", marker=dict(color=PURPLE, cornerradius=6),
                         customdata=cd, hovertemplate="<b>%{x}</b><br>Laba kotor $%{y:,.0f}"
                         "<extra>klik untuk detail</extra>", unselected=dict(marker=dict(opacity=0.4))))
    fig.update_yaxes(title="Nilai (US$)", tickprefix="$", tickformat="~s")
    fig.update_xaxes(title="Bulan" if freq == "month" else "Minggu (tanggal awal)", type="category",
                     tickangle=-45 if len(x) > 14 else 0)
    fig = _base(fig, 340, legend=True)
    fig.update_layout(barmode="group", bargap=0.3, bargroupgap=0.08)
    return fig


# ================================================================== batang horizontal ber-track
def hbar(labels, values, keys, *, title_x: str, title_y: str, fmt: str = "money", height: int | None = None,
         extra=None, extra_name: str = "", color=None, max_value: float | None = None) -> go.Figure:
    """Batang horizontal dengan track abu muda. `extra` = nilai tambahan di hover."""
    labels, values = list(labels), np.asarray(values, dtype=float)
    mx = max_value if max_value is not None else (values.max() if len(values) else 1) * 1.0
    if fmt == "money":
        txt = [f"${nf(v / 1e6, 2)} jt" if v >= 1e6 else (f"${nf(v / 1e3, 0)} rb" if v >= 1e4 else f"${nf(v, 0)}") for v in values]
        hov = "$%{x:,.0f}"
    elif fmt == "pct":
        txt = [f"{nf(v, 1)}%" for v in values]
        hov = "%{x:.1f}%"
    else:
        txt = [nf(v, 0) for v in values]
        hov = "%{x:,.0f}"
    ex = extra if extra is not None else [""] * len(values)
    cd = np.stack([keys, ex], axis=1)
    fig = go.Figure()
    fig.add_trace(go.Bar(y=labels, x=[mx] * len(values), orientation="h", marker=dict(color=TRACK, cornerradius=8),
                         hoverinfo="skip", customdata=cd, showlegend=False,
                         selected=dict(marker=dict(opacity=1)), unselected=dict(marker=dict(opacity=1))))
    fig.add_trace(go.Bar(y=labels, x=values, orientation="h",
                         marker=dict(color=color if color is not None else PURPLE, cornerradius=8),
                         text=txt, textposition="outside", cliponaxis=False, textfont=dict(size=11, color=NAVY),
                         customdata=cd, showlegend=False,
                         hovertemplate="<b>%{y}</b><br>" + hov + (f"<br>{extra_name}: %{{customdata[1]}}" if extra is not None else "")
                         + "<extra>klik untuk detail</extra>", unselected=dict(marker=dict(opacity=0.4))))
    fig.update_xaxes(title=title_x, range=[0, mx * 1.28], showgrid=False, showticklabels=False)
    fig.update_yaxes(title=title_y, autorange="reversed", showgrid=False)
    fig = _base(fig, height or (34 * len(labels) + 70))
    fig.update_layout(barmode="overlay", bargap=0.38)
    return fig


# ================================================================== diskon
def discount_margin(dt: pd.DataFrame) -> go.Figure:
    colors = [RED if m < 5 else (PURPLE_L if m < 30 else PURPLE) for m in dt.margin]
    fig = go.Figure(go.Bar(
        x=dt.disc_bin.astype(str), y=dt.margin, marker=dict(color=colors, cornerradius=8),
        text=[f"{nf(m, 1)}%" for m in dt.margin], textposition="outside", cliponaxis=False,
        textfont=dict(size=12, color=NAVY),
        customdata=np.stack([dt.disc_bin.astype(str), dt.rows, dt.loss_rate, dt.qty], axis=1),
        hovertemplate="<b>Diskon %{x}</b><br>Margin %{y:.1f}%<br>%{customdata[1]} transaksi · "
                      "%{customdata[2]:.1f}% rugi<extra>klik untuk detail</extra>",
        unselected=dict(marker=dict(opacity=0.4))))
    fig.update_yaxes(title="Margin laba kotor (%)", ticksuffix="%", range=[min(0, dt.margin.min()) - 4, dt.margin.max() * 1.18])
    fig.update_xaxes(title="Besar diskon pada transaksi")
    fig.add_hline(y=0, line=dict(color=MUTED, width=1))
    return _base(fig, 330)


def discount_qty(dt: pd.DataFrame) -> go.Figure:
    mx = dt.qty.max() * 1.3
    fig = go.Figure()
    fig.add_trace(go.Bar(x=dt.disc_bin.astype(str), y=[mx] * len(dt), marker=dict(color=TRACK, cornerradius=8),
                         hoverinfo="skip", showlegend=False))
    fig.add_trace(go.Bar(x=dt.disc_bin.astype(str), y=dt.qty, marker=dict(color=PURPLE_L, cornerradius=8),
                         text=[nf(v, 2) for v in dt.qty], textposition="outside", cliponaxis=False,
                         textfont=dict(size=12, color=NAVY),
                         hovertemplate="<b>Diskon %{x}</b><br>%{y:.2f} barang per transaksi<extra></extra>"))
    fig.update_yaxes(title="Rata-rata barang per transaksi", range=[0, mx * 1.05])
    fig.update_xaxes(title="Besar diskon pada transaksi")
    fig = _base(fig, 330)
    fig.update_layout(barmode="overlay", clickmode="none")
    return fig


def cap_curve(caps, gains, current: float) -> go.Figure:
    fig = go.Figure(go.Scatter(x=caps, y=gains, mode="lines", line=dict(color=PURPLE, width=3, shape="spline"),
                               fill="tozeroy", fillcolor="rgba(67,24,255,0.08)",
                               hovertemplate="Batas diskon %{x}%<br>Tambahan laba $%{y:,.0f}<extra></extra>"))
    cur = float(np.interp(current, caps, gains))
    fig.add_trace(go.Scatter(x=[current], y=[cur], mode="markers", hoverinfo="skip",
                             marker=dict(size=14, color=PURPLE, line=dict(width=3, color="white"))))
    fig.update_xaxes(title="Batas maksimum diskon (%)", ticksuffix="%", dtick=10)
    fig.update_yaxes(title="Perkiraan tambahan laba (US$)", tickprefix="$", tickformat="~s", rangemode="tozero")
    fig = _base(fig, 280)
    fig.update_layout(clickmode="none")
    return fig


# ================================================================== heatmap hari x jam
def day_hour(h: pd.DataFrame) -> go.Figure:
    h = h.reindex(DAYS).fillna(0)
    days = [DAYS_ID[d] for d in h.index]
    hours = [f"{int(c):02d}" for c in h.columns]
    fig = go.Figure(go.Heatmap(z=h.values, x=hours, y=days, colorscale=SEQ, xgap=2, ygap=2, hoverinfo="skip",
                               colorbar=dict(title=dict(text="Transaksi", side="right", font=dict(size=11)),
                                             thickness=10, len=0.9, outlinewidth=0, tickfont=dict(size=10, color=MUTED))))
    xx, yy, cc, kk = [], [], [], []
    for i, d in enumerate(h.index):
        for j, c in enumerate(h.columns):
            xx.append(hours[j]); yy.append(days[i]); cc.append(h.values[i, j]); kk.append(f"{d}|{int(c)}")
    fig.add_trace(go.Scatter(x=xx, y=yy, mode="markers", marker=dict(symbol="square", size=16, color="rgba(0,0,0,0.002)"),
                             customdata=np.stack([kk, cc], axis=1),
                             hovertemplate="<b>%{y}, pukul %{x}.00</b><br>%{customdata[1]} transaksi<extra>klik untuk detail</extra>",
                             selected=dict(marker=dict(opacity=1)), unselected=dict(marker=dict(opacity=1))))
    fig.update_xaxes(title="Jam belanja", type="category", showline=False)
    fig.update_yaxes(title="Hari", type="category", autorange="reversed", showgrid=False)
    return _base(fig, 330)


# ================================================================== produk & kategori
def category_bubble(cat: pd.DataFrame) -> go.Figure:
    size = np.sqrt(cat.units / cat.units.max()) * 42 + 6
    fig = go.Figure(go.Scatter(
        x=cat.revenue, y=cat.margin, mode="markers",
        marker=dict(size=size, color=cat.margin, colorscale=SEQ, cmin=cat.margin.min() - 2, cmax=cat.margin.max(),
                    line=dict(width=1.5, color="white"), opacity=0.9, showscale=False),
        customdata=np.stack([cat.product_category.astype(str), cat.product_department.astype(str), cat.units], axis=1),
        hovertemplate="<b>%{customdata[0]}</b> (%{customdata[1]})<br>Penjualan $%{x:,.0f}<br>Margin %{y:.1f}%"
                      "<br>%{customdata[2]:,} unit<extra>klik untuk detail</extra>",
        unselected=dict(marker=dict(opacity=0.35))))
    avg_m = cat.profit.sum() / cat.revenue.sum() * 100
    fig.add_hline(y=avg_m, line=dict(color=MUTED, width=1, dash="dot"))
    fig.add_annotation(xref="paper", x=1, y=avg_m, text=f"rata-rata<br>{nf(avg_m, 1)}%", showarrow=False,
                       xanchor="left", xshift=4, font=dict(size=10, color=MUTED2))
    for _, r in pd.concat([cat.nlargest(1, "margin"), cat.nsmallest(1, "margin"), cat.nlargest(1, "revenue")]).drop_duplicates("product_category").iterrows():
        fig.add_annotation(x=r.revenue, y=r.margin, text=str(r.product_category), showarrow=True, arrowhead=0,
                           arrowcolor=MUTED, ax=0, ay=-28, font=dict(size=11, color=NAVY), bgcolor="rgba(255,255,255,.85)")
    fig.update_xaxes(title="Penjualan bersih (US$) · ukuran gelembung = unit terjual", tickprefix="$", tickformat="~s",
                     showgrid=True, gridcolor=GRID, griddash="dot")
    fig.update_yaxes(title="Margin laba kotor (%)", ticksuffix="%")
    fig = _base(fig, 420)
    fig.update_layout(margin=dict(l=8, r=80, t=16, b=8))
    return fig


def pareto_curve(p: pd.DataFrame, what: str) -> go.Figure:
    fig = go.Figure(go.Scatter(x=p.share_items, y=p.share_rev, mode="lines", line=dict(color=PURPLE, width=3),
                               fill="tozeroy", fillcolor="rgba(67,24,255,0.08)",
                               hovertemplate=f"%{{x:.1f}}% {what} teratas<br>menyumbang %{{y:.1f}}% penjualan<extra></extra>"))
    fig.add_trace(go.Scatter(x=[0, 100], y=[0, 100], mode="lines", line=dict(color=MUTED, width=1, dash="dot"),
                             hoverinfo="skip"))
    y20 = float(np.interp(20, p.share_items, p.share_rev))
    fig.add_trace(go.Scatter(x=[20], y=[y20], mode="markers", marker=dict(size=12, color=PURPLE, line=dict(width=3, color="white")),
                             hoverinfo="skip"))
    fig.add_annotation(x=20, y=y20, text=f"<b>20% {what}</b> teratas<br>= {nf(y20, 0)}% penjualan", showarrow=True,
                       arrowhead=0, axref="x", ayref="y", ax=52, ay=22, xanchor="left", align="left",
                       font=dict(size=11, color=NAVY), bgcolor="rgba(255,255,255,.95)", arrowcolor=MUTED)
    fig.add_annotation(x=98, y=6, text="garis titik-titik = penjualan merata", showarrow=False, xanchor="right",
                       font=dict(size=10, color=MUTED))
    fig.update_xaxes(title=f"% {what} (diurutkan dari penjualan terbesar)", ticksuffix="%", range=[0, 100], dtick=20)
    fig.update_yaxes(title="% kumulatif penjualan", ticksuffix="%", range=[0, 102], dtick=20)
    fig = _base(fig, 330)
    fig.update_layout(clickmode="none")
    return fig


# ================================================================== pelanggan
def freq_bars(cf: pd.DataFrame) -> go.Figure:
    fig = go.Figure(go.Bar(
        x=[f"{f} kali" for f in cf.freq.astype(str)], y=cf.share_c, marker=dict(color=[PURPLE] + [PURPLE_L] * (len(cf) - 1), cornerradius=8),
        text=[f"{nf(v, 1)}%" for v in cf.share_c], textposition="outside", cliponaxis=False, textfont=dict(size=12, color=NAVY),
        customdata=np.stack([cf.freq.astype(str), cf.customers, cf.share_rev, cf.avg], axis=1),
        hovertemplate="<b>Belanja %{x}</b><br>%{customdata[1]:,} pelanggan (%{y:.1f}%)<br>Menyumbang %{customdata[2]:.1f}% "
                      "penjualan<br>Rata-rata belanja $%{customdata[3]:,.0f}<extra>klik untuk detail</extra>",
        unselected=dict(marker=dict(opacity=0.4))))
    fig.update_xaxes(title="Jumlah transaksi per pelanggan dalam periode")
    fig.update_yaxes(title="% pelanggan", ticksuffix="%", range=[0, cf.share_c.max() * 1.2])
    return _base(fig, 300)


def histogram(values, *, title_x: str, title_y: str, bins: int = 20, color: str = PURPLE_L, prefix: str = "") -> go.Figure:
    counts, edges = np.histogram(values, bins=bins)
    mids = (edges[:-1] + edges[1:]) / 2
    lab = [f"{prefix}{nf(a, 0)}–{prefix}{nf(b, 0)}" for a, b in zip(edges[:-1], edges[1:])]
    fig = go.Figure(go.Bar(x=mids, y=counts, width=(edges[1] - edges[0]) * 0.86, marker=dict(color=color, cornerradius=4),
                           customdata=lab, hovertemplate="%{customdata}<br>%{y:,}<extra></extra>"))
    fig.update_xaxes(title=title_x, tickprefix=prefix)
    fig.update_yaxes(title=title_y)
    fig = _base(fig, 280)
    fig.update_layout(clickmode="none")
    return fig


# ================================================================== pemasok
def supplier_scatter(s: pd.DataFrame) -> go.Figure:
    size = np.sqrt(s.revenue / s.revenue.max()) * 30 + 6
    fig = go.Figure(go.Scatter(
        x=s.ontime * 100, y=s.defect * 100, mode="markers",
        marker=dict(size=size, color=s.score, colorscale=SEQ, cmin=0, cmax=100, line=dict(width=1.5, color="white"),
                    colorbar=dict(title=dict(text="Skor", side="right", font=dict(size=11)), thickness=10, len=0.9,
                                  outlinewidth=0, tickfont=dict(size=10, color=MUTED))),
        customdata=np.stack([s.supplier_id, s.supplier_type, s.lead.round(1), s.score.round(0), s.revenue], axis=1),
        hovertemplate="<b>%{customdata[0]}</b> (%{customdata[1]})<br>Tepat waktu %{x:.1f}% · cacat %{y:.2f}%"
                      "<br>Lead time %{customdata[2]} hari · skor %{customdata[3]}<br>Penjualan $%{customdata[4]:,.0f}"
                      "<extra>klik untuk detail</extra>",
        unselected=dict(marker=dict(opacity=0.35))))
    fig.add_annotation(xref="paper", yref="paper", x=1, y=0, text="↘ kanan-bawah = terbaik", showarrow=False,
                       xanchor="right", yanchor="bottom", font=dict(size=10, color=MUTED2))
    fig.update_xaxes(title="Rata-rata pengiriman tepat waktu (%) · ukuran = penjualan", ticksuffix="%",
                     showgrid=True, gridcolor=GRID, griddash="dot")
    fig.update_yaxes(title="Rata-rata tingkat cacat (%)", ticksuffix="%")
    return _base(fig, 400)


# ================================================================== mini tren (dialog)
def mini_trend(g: pd.DataFrame, x: str, y: str = "revenue", ytitle: str = "Penjualan bersih (US$)",
               xtitle: str = "Bulan") -> go.Figure:
    xs = [_month_label(t) for t in g[x]] if x == "month" else g[x]
    fig = go.Figure(go.Scatter(x=xs, y=g[y], mode="lines+markers", line=dict(color=PURPLE, width=3, shape="spline"),
                               marker=dict(size=6, color=PURPLE), fill="tozeroy", fillcolor="rgba(67,24,255,0.07)",
                               hovertemplate="%{x}<br>$%{y:,.0f}<extra></extra>"))
    fig.update_xaxes(title=xtitle, type="category", tickangle=-45 if len(xs) > 14 else 0)
    fig.update_yaxes(title=ytitle, tickprefix="$", tickformat="~s", rangemode="tozero")
    fig = _base(fig, 240)
    fig.update_layout(clickmode="none")
    return fig
