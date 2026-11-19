"""Dashboard Analitik Supermarket — Streamlit (gaya visual terinspirasi template Venus).

Jalankan lokal:  streamlit run app.py
Klik batang / titik / sel / baris tabel untuk membuka detail.
"""
from __future__ import annotations

import html
import re
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

from src import charts as C
from src import metrics as M
from src.data import DAYS_ID, MONTHS_ID, load_data, load_report, money, nf, setting

st.set_page_config(page_title="Analitik Supermarket", page_icon="🛒", layout="wide", initial_sidebar_state="auto")

REFRESH = int(setting("AUTO_REFRESH_SECONDS", "0"))
ss = st.session_state
ss.setdefault("nonce", 0)

_css = (Path(__file__).parent / "assets" / "style.css").read_text()
st.markdown("<style>" + "\n".join(l for l in _css.splitlines() if l.strip()) + "</style>", unsafe_allow_html=True)


# ======================================================================= helper UI
def ms(name: str) -> str:
    return f'<span class="ms">{name}</span>'


def card_title(title: str, sub: str = ""):
    st.markdown(f'<p class="card-t">{title}</p>' + (f'<p class="card-s">{sub}</p>' if sub else ""), unsafe_allow_html=True)


def howto(text: str, icon: str = "touch_app"):
    st.markdown(f'<div class="howto">{ms(icon)}<div>{text}</div></div>', unsafe_allow_html=True)


def note(text: str):
    st.markdown(f'<div class="note">{text}</div>', unsafe_allow_html=True)


def badge(v: float, d: int = 1, unit: str = "%", invert: bool = False) -> str:
    if abs(v) < (0.05 if d else 0.5):
        return f'<span class="badge n">±0{unit}</span>'
    good = (v > 0) ^ invert
    return f'<span class="badge {"g" if good else "r"}">{"▲" if v > 0 else "▼"} {nf(abs(v), d)}{unit}</span>'


def bold(t: str) -> str:
    return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)


def mini(items) -> str:
    return '<div class="mini">' + "".join(
        f'<div class="mbox"><div class="l">{l}</div><div class="v">{v}</div>' + (f'<div class="s">{s}</div>' if s else "")
        + "</div>" for l, v, s in items) + "</div>"


clicks: list[tuple[str, dict, dict]] = []


def clickable(fig, name: str, kind: str, ctx: dict | None = None):
    ev = st.plotly_chart(fig, key=f"{name}_{ss.nonce}", on_select="rerun", selection_mode="points", config=C.CONFIG)
    pts = (ev or {}).get("selection", {}).get("points", []) if ev else []
    if pts:
        clicks.append((kind, pts[0], ctx or {}))


def static_chart(fig, key: str):
    st.plotly_chart(fig, key=key, config=C.CONFIG)


def table_click(df_show: pd.DataFrame, key: str, kind: str, id_col: str, height: int = 380, column_config=None):
    ev = st.dataframe(df_show, hide_index=True, height=height, key=f"{key}_{ss.nonce}", on_select="rerun",
                      selection_mode="single-row", column_config=column_config or {})
    if ev and ev.selection.rows:
        clicks.append((kind, {"customdata": [df_show.iloc[ev.selection.rows[0]][id_col]]}, {}))


def reset_selection():
    ss.nonce += 1


# ======================================================================= data
df_all, source_info = load_data()
report = load_report()
stamp = source_info.split(" · ")[1] if " · " in source_info else source_info
src_name = source_info.split(" · ")[0]

PAGES = {
    "Ringkasan": (":material/space_dashboard: Ringkasan", "Kinerja penjualan & laba, kapan pelanggan berbelanja, dan temuan utama."),
    "Diskon & profitabilitas": (":material/sell: Diskon & profitabilitas", "Seberapa besar diskon menggerus laba — dan berapa yang bisa diselamatkan."),
    "Produk & kategori": (":material/inventory_2: Produk & kategori", "Kategori paling menguntungkan dan konsentrasi penjualan produk."),
    "Pelanggan": (":material/group: Pelanggan", "Frekuensi belanja, konsentrasi, dan komposisi pelanggan."),
    "Toko & wilayah": (":material/storefront: Toko & wilayah", "Kinerja 200 toko per wilayah dan tipe toko."),
    "Pemasok & operasional": (":material/local_shipping: Pemasok & operasional", "Scorecard pemasok, pengiriman, retur, dan keluhan."),
    "Kualitas data": (":material/fact_check: Kualitas data", "Apa yang bisa dan tidak bisa dipercaya dari dataset ini."),
}

with st.sidebar:
    st.markdown(f"""<div class="brand"><div class="ic">{ms('shopping_cart')}</div>
      <div><b>SUPERMARKET</b><small>Analytics</small></div></div>""", unsafe_allow_html=True)
    page = st.radio("Menu", list(PAGES), format_func=lambda p: PAGES[p][0], key="page", label_visibility="collapsed")
    st.markdown(f"""<div class="side-card"><div class="ic">{ms('database')}</div>
      <b>Sumber data: {html.escape(src_name)}</b><p>{nf(len(df_all))} transaksi bersih<br>{html.escape(stamp)}</p></div>""",
                unsafe_allow_html=True)
    st.markdown("<div style='height:.6rem'></div>", unsafe_allow_html=True)
    if st.button("Muat ulang data", icon=":material/refresh:", width="stretch"):
        load_data.clear()
        st.rerun()

# ======================================================================= header + filter global
dmin, dmax = df_all.date.min().date(), df_all.date.max().date()
CATS = {
    "f_region": ("store_region", "Wilayah toko"),
    "f_stype": ("store_type", "Tipe toko"),
    "f_dept": ("product_department", "Departemen produk"),
    "f_seg": ("customer_segment", "Segmen pelanggan"),
}
OPTS = {k: sorted(df_all[c].astype(str).unique()) for k, (c, _) in CATS.items()}
for k in CATS:
    ss.setdefault(k, [])
ss.setdefault("f_date", (dmin, dmax))


def _reset_filters():
    for k in CATS:
        ss[k] = []
    ss.f_date = (dmin, dmax)


active = [f"{lab}: {', '.join(ss[k])}" for k, (c, lab) in CATS.items() if ss.get(k)]
dr = ss.get("f_date", (dmin, dmax))
if isinstance(dr, (tuple, list)) and len(dr) == 2 and tuple(dr) != (dmin, dmax):
    active.append(f"Periode {dr[0]:%d/%m/%y}–{dr[1]:%d/%m/%y}")

with st.container(key="hdr"):
    h1, h2, h3 = st.columns([3, 1.1, 1.3], vertical_alignment="center")
    h1.markdown(f'<p class="crumb"><span>Halaman</span> / {page}</p><p class="page-t">{page}</p>'
                f'<p class="page-d">{PAGES[page][1]}</p>', unsafe_allow_html=True)
    with h2.popover(f"Filter{f' · {len(active)}' if active else ''}", icon=":material/tune:", width="stretch"):
        st.caption("Filter berlaku untuk semua halaman. Kosong = semua.")
        st.date_input("Periode transaksi", min_value=dmin, max_value=dmax, key="f_date", format="DD/MM/YYYY")
        for k in ("f_region", "f_stype"):
            st.pills(CATS[k][1], OPTS[k], selection_mode="multi", key=k)
        for k in ("f_dept", "f_seg"):
            st.multiselect(CATS[k][1], OPTS[k], key=k, placeholder="Semua")
        st.button("Reset filter", on_click=_reset_filters, width="stretch", icon=":material/restart_alt:")
    h3.markdown(f'<div class="livewrap"><span class="chip-live"><i></i>{html.escape(stamp)}</span></div>', unsafe_allow_html=True)
if active:
    st.markdown('<div class="fchips">' + "".join(f'<span class="fchip">{html.escape(a)}</span>' for a in active) + "</div>",
                unsafe_allow_html=True)

mask = pd.Series(True, index=df_all.index)
for k, (c, _) in CATS.items():
    if ss.get(k):
        mask &= df_all[c].astype(str).isin(ss[k])
if isinstance(dr, (tuple, list)) and len(dr) == 2:
    mask &= df_all.date.between(pd.Timestamp(dr[0]), pd.Timestamp(dr[1]))
df = df_all[mask]
if df.empty:
    st.warning("Tidak ada transaksi untuk kombinasi filter ini. Buka **Filter → Reset filter**.")
    st.stop()

K = M.kpis(df)
K_all = M.kpis(df_all)
filtered = len(df) < len(df_all)


def kpi(label, value, sub, icon, hl=False):
    return (f'<div class="kpi{" hl" if hl else ""}"><div class="ic">{ms(icon)}</div><div style="min-width:0">'
            f'<div class="l">{label}</div><div class="v">{value}</div><div class="s">{sub}</div></div></div>')


if page != "Kualitas data":
    st.markdown('<div class="kpis">' + "".join([
        kpi("Penjualan bersih", money(K["revenue"]),
            f"{nf(K['revenue'] / K_all['revenue'] * 100, 0)}% dari total" if filtered else f"{MONTHS_ID[dmin.month - 1]} {dmin.year}–{MONTHS_ID[dmax.month - 1]} {dmax.year}",
            "payments", hl=True),
        kpi("Laba kotor", money(K["profit"]), "penjualan − HPP", "account_balance_wallet"),
        kpi("Margin kotor", f"{nf(K['margin'], 1)}%", (badge(K["margin"] - K_all["margin"], 1, " pp") + " vs semua")
            if filtered else "laba ÷ penjualan", "percent"),
        kpi("Transaksi", nf(K["tx"]), f"{nf(K['customers'])} pelanggan", "receipt_long"),
        kpi("Nilai per transaksi", f"${nf(K['aov'], 2)}", f"≈ {nf(K['units'] / K['tx'], 1)} barang", "shopping_basket"),
    ]) + "</div>", unsafe_allow_html=True)

# ======================================================================= 1. Ringkasan
if page == "Ringkasan":
    with st.container(key="row_r1"):
        c1, c2 = st.columns([1.9, 1])
        with c1, st.container(key="card_trend"):
            a, b = st.columns([2, 1], vertical_alignment="bottom")
            with a:
                card_title("Penjualan & laba kotor", "batang muda = penjualan bersih · batang ungu = laba kotor")
            freq = b.segmented_control("Periode", ["Bulanan", "Mingguan"], default="Bulanan", key="trend_freq",
                                       label_visibility="collapsed") or "Bulanan"
            fk = "month" if freq == "Bulanan" else "week"
            g = M.by_period(df, fk)
            cv = g.revenue.std() / g.revenue.mean() * 100 if len(g) > 1 else 0
            howto(f"Klik batang untuk rincian periode. Variasi antar {'bulan' if fk == 'month' else 'minggu'} hanya "
                  f"<b>{nf(cv, 1)}%</b> — penjualan sangat stabil, tanpa pola musiman.")
            clickable(C.trend(g, fk), f"trend_{fk}", "period", {"freq": fk})
        with c2, st.container(key="card_dept"):
            dep = M.agg(df, "product_department")
            card_title("Porsi penjualan per departemen", f"<b>{dep.iloc[0].product_department}</b> terbesar "
                       f"({nf(dep.iloc[0].share, 0)}% penjualan)")
            howto("Klik departemen untuk melihat kategorinya.")
            clickable(C.hbar(dep.product_department.astype(str), dep.revenue, dep.product_department.astype(str),
                             title_x="Penjualan bersih (US$)", title_y="Departemen",
                             extra=[f"{nf(m, 1)}% margin · {nf(s, 1)}% porsi" for m, s in zip(dep.margin, dep.share)],
                             extra_name="Info"), "dept", "dept")
    with st.container(key="row_r2"):
        c1, c2 = st.columns([1.9, 1])
        with c1, st.container(key="card_heat"):
            peak = df.shopping_hour.between(7, 10).mean() * 100
            card_title("Kapan pelanggan berbelanja", f"jumlah transaksi per hari × jam · <b>{nf(peak, 0)}%</b> transaksi "
                       "terjadi pukul 07.00–10.59")
            howto("Klik sebuah sel untuk melihat apa yang dibeli pada jam tersebut.")
            clickable(C.day_hour(M.heat_day_hour(df)), "heat", "dayhour")
        with c2, st.container(key="card_ins"):
            card_title("Temuan utama", "dihitung ulang otomatis dari data & filter")
            st.markdown('<ul class="tl">' + "".join(f"<li>{bold(t)}</li>" for t in M.insights(df)) + "</ul>",
                        unsafe_allow_html=True)

# ======================================================================= 2. Diskon & profitabilitas
elif page == "Diskon & profitabilitas":
    dt = M.discount_table(df)
    with st.container(key="card_dsum"):
        card_title("Ringkasan diskon", "semua angka mengikuti filter")
        st.markdown(mini([
            ("Total diskon diberikan", money(K["discount"]), f"{nf(K['discount'] / K['gross'] * 100, 1)}% dari penjualan kotor"),
            ("Diskon di atas 20%", money(df.loc[df.discount_percent > 20, 'discount_value'].sum()),
             f"{nf((df.discount_percent > 20).mean() * 100, 1)}% transaksi"),
            ("Transaksi rugi", f"{nf(K['loss_rows'] / K['tx'] * 100, 1)}%", f"{nf(K['loss_rows'])} baris"),
            ("Total kerugian", money(K["loss_sum"]), "laba kotor negatif"),
        ]), unsafe_allow_html=True)
    with st.container(key="row_d1"):
        c1, c2 = st.columns(2)
        with c1, st.container(key="card_dm"):
            card_title("Margin turun tajam seiring diskon",
                       f"dari <b>{nf(dt.iloc[0].margin, 1)}%</b> tanpa diskon ke <b>{nf(dt.iloc[-1].margin, 1)}%</b> "
                       f"pada diskon {dt.iloc[-1].disc_bin} · merah = hampir/sudah rugi")
            howto("Klik batang untuk melihat transaksi pada tingkat diskon tersebut.")
            clickable(C.discount_margin(dt), "dmargin", "disc")
        with c2, st.container(key="card_dq"):
            card_title("…tetapi volume pembelian tidak naik",
                       f"rata-rata barang per transaksi tetap <b>{nf(dt.qty.min(), 2)}–{nf(dt.qty.max(), 2)}</b> di semua tingkat diskon")
            note("Artinya diskon besar <b>tidak menarik pembelian lebih banyak</b> — ia hanya mengurangi pendapatan per barang. "
                 "Sumbu Y dimulai dari 0 agar perbandingan jujur.")
            static_chart(C.discount_qty(dt), "dqty")
    with st.container(key="row_d2"):
        c1, c2 = st.columns([1.35, 1])
        with c1, st.container(key="card_cap"):
            card_title("Simulasi: batasi diskon maksimum",
                       "perkiraan laba bila diskon di atas batas diturunkan ke batas (volume diasumsikan tetap)")
            cap = st.slider("Batas maksimum diskon (%)", 0, 50, 20, step=1, key="cap")
            r = M.discount_cap(df, cap)
            st.markdown(mini([
                ("Tambahan laba", money(r["gain"]), f"{badge(r['gain'] / r['profit_now'] * 100, 1)} dari laba sekarang"),
                ("Margin baru", f"{nf(r['margin_new'], 1)}%", f"sekarang {nf(r['margin_now'], 1)}%"),
                ("Transaksi terdampak", f"{nf(r['affected_pct'], 1)}%", f"{nf(r['affected'])} baris"),
                ("Transaksi rugi tersisa", nf(r["loss_rows_new"]), f"sekarang {nf(K['loss_rows'])}"),
            ]), unsafe_allow_html=True)
            caps = list(range(0, 51, 2))
            gains = [M.discount_cap(df, c)["gain"] for c in caps]
            static_chart(C.cap_curve(caps, gains, cap), "capcurve")
            st.caption("Asumsi didukung data: jumlah barang per transaksi tidak berubah antar tingkat diskon. "
                       "Dampak nyata pada jumlah pelanggan tidak bisa diukur dari data ini.")
        with c2, st.container(key="card_promo"):
            pr = M.agg(df, "promotion_type", sort="margin")
            spread = pr.margin.max() - pr.margin.min()
            card_title("Jenis promosi hampir tidak berpengaruh",
                       f"margin semua jenis promosi berbeda hanya <b>{nf(spread, 1)} poin</b> — yang menentukan adalah besar diskonnya")
            howto("Klik jenis promosi untuk rinciannya.")
            clickable(C.hbar(pr.promotion_type.astype(str), pr.margin, pr.promotion_type.astype(str), fmt="pct",
                             title_x="Margin laba kotor (%)", title_y="Jenis promosi",
                             extra=[f"{nf(q, 2)} barang/transaksi · diskon rata-rata {nf(d, 1)}%" for q, d in zip(pr.qty, pr.disc_pct)],
                             extra_name="Volume", max_value=max(pr.margin.max(), 1)), "promo", "promo")
    with st.container(key="card_be"):
        be = M.category_breakeven(df)
        card_title("Kategori dengan kerugian diskon terbesar",
                   "titik impas = diskon maksimum sebelum transaksi rugi (median per kategori) · klik baris untuk detail kategori")
        be = be.assign(loss=-be.loss)
        show = be[["product_category", "break_even", "disc", "beyond", "loss", "margin", "revenue"]].rename(columns={
            "product_category": "Kategori", "break_even": "Titik impas diskon (%)", "disc": "Diskon rata-rata (%)",
            "beyond": "% transaksi rugi", "loss": "Total kerugian (US$)", "margin": "Margin (%)", "revenue": "Penjualan (US$)"})
        table_click(show, "betbl", "cat", "Kategori", height=360, column_config={
            "Titik impas diskon (%)": st.column_config.NumberColumn(format="%.1f%%"),
            "Diskon rata-rata (%)": st.column_config.NumberColumn(format="%.1f%%"),
            "% transaksi rugi": st.column_config.ProgressColumn(min_value=0, max_value=float(max(be.beyond.max(), 1)), format="%.1f%%"),
            "Total kerugian (US$)": st.column_config.NumberColumn(format="$%.0f"),
            "Margin (%)": st.column_config.NumberColumn(format="%.1f%%"),
            "Penjualan (US$)": st.column_config.NumberColumn(format="$%.0f"),
        })

# ======================================================================= 3. Produk & kategori
elif page == "Produk & kategori":
    cat = M.agg(df, ["product_category", "product_department"])
    with st.container(key="row_p1"):
        c1, c2 = st.columns([1.7, 1])
        with c1, st.container(key="card_bubble"):
            card_title("Peta kategori: penjualan vs margin",
                       f"{len(cat)} kategori · margin berkisar <b>{nf(cat.margin.min(), 1)}%</b>–<b>{nf(cat.margin.max(), 1)}%</b>, "
                       "dipengaruhi rasio biaya terhadap harga")
            howto("Klik gelembung untuk melihat subkategori & produk di kategori tersebut.")
            clickable(C.category_bubble(cat), "bubble", "cat")
        with c2, st.container(key="card_pareto"):
            card_title("Konsentrasi penjualan produk", f"{nf(df.product_id.nunique())} produk terjual")
            static_chart(C.pareto_curve(M.pareto(df, "product_id"), "produk"), "pareto_p")
    with st.container(key="row_p2"):
        c1, c2 = st.columns([1.7, 1])
        with c1, st.container(key="card_prod"):
            card_title("Daftar produk", "klik baris untuk profil produk · klik judul kolom untuk mengurutkan")
            with st.container(key="ctl_prod"):
                a, b = st.columns(2)
                metric = a.selectbox("Urutkan menurut", ["Penjualan", "Laba kotor", "Margin", "Unit terjual"], key="prod_metric")
                order = b.segmented_control("Tampilkan", ["Teratas", "Terbawah"], default="Teratas", key="prod_order") or "Teratas"
            p = df.groupby(["product_id", "product_name", "product_category", "brand"], observed=True).agg(
                revenue=("net_sales", "sum"), profit=("gross_profit", "sum"), units=("quantity", "sum"),
                rows=("transaction_id", "size")).reset_index()
            p = p[p.rows >= 3]
            p["margin"] = p.profit / p.revenue * 100
            col = {"Penjualan": "revenue", "Laba kotor": "profit", "Margin": "margin", "Unit terjual": "units"}[metric]
            p = p.sort_values(col, ascending=(order == "Terbawah")).head(50)
            show = p[["product_name", "product_category", "revenue", "profit", "margin", "units"]].rename(columns={
                "product_name": "Produk", "product_category": "Kategori",
                "revenue": "Penjualan (US$)", "profit": "Laba (US$)", "margin": "Margin (%)", "units": "Unit"})
            table_click(show, "prodtbl", "product", "Produk", height=400, column_config={
                "Penjualan (US$)": st.column_config.NumberColumn(format="$%.0f"),
                "Laba (US$)": st.column_config.NumberColumn(format="$%.0f"),
                "Margin (%)": st.column_config.NumberColumn(format="%.1f%%")})
            st.caption("Hanya produk dengan ≥3 transaksi agar margin tidak bias oleh satu transaksi.")
        with c2, st.container(key="card_brand"):
            card_title("Tipe merek & segmen produk", "porsi penjualan · klik untuk detail")
            bt = M.agg(df, "brand_type")
            clickable(C.hbar(bt.brand_type.astype(str), bt.share, bt.brand_type.astype(str), fmt="pct",
                             title_x="Porsi penjualan (%)", title_y="Tipe merek",
                             extra=[f"{nf(m, 1)}%" for m in bt.margin], extra_name="Margin", max_value=bt.share.max()),
                      "brandtype", "group", {"col": "brand_type"})
            sg = M.agg(df, "product_segment")
            clickable(C.hbar(sg.product_segment.astype(str), sg.share, sg.product_segment.astype(str), fmt="pct",
                             title_x="Porsi penjualan (%)", title_y="Segmen produk",
                             extra=[f"{nf(m, 1)}%" for m in sg.margin], extra_name="Margin", max_value=sg.share.max()),
                      "segment", "group", {"col": "product_segment"})

# ======================================================================= 4. Pelanggan
elif page == "Pelanggan":
    cf = M.customer_freq(df)
    once = cf.loc[cf.freq == "1", "share_c"].sum()
    with st.container(key="card_csum"):
        card_title("Ringkasan pelanggan")
        st.markdown(mini([
            ("Pelanggan unik", nf(K["customers"]), f"{nf(K['tx'] / K['customers'], 2)} transaksi per pelanggan"),
            ("Hanya belanja sekali", f"{nf(once, 1)}%", "dalam periode terpilih"),
            ("20% pelanggan teratas", f"{nf(M.top_share(df, 'customer_id'), 0)}%", "dari total penjualan"),
            ("Belanja rata-rata per pelanggan", f"${nf(K['revenue'] / K['customers'], 2)}", "total periode"),
        ]), unsafe_allow_html=True)
    with st.container(key="row_c1"):
        c1, c2 = st.columns(2)
        with c1, st.container(key="card_freq"):
            card_title("Seberapa sering pelanggan kembali", f"<b>{nf(once, 0)}%</b> pelanggan hanya bertransaksi sekali")
            howto("Klik batang untuk profil kelompok pelanggan tersebut.")
            clickable(C.freq_bars(cf), "freq", "freq")
        with c2, st.container(key="card_conc"):
            card_title("Konsentrasi penjualan pelanggan", "kurva makin melengkung = makin bergantung pada sedikit pelanggan")
            static_chart(C.pareto_curve(M.pareto(df, "customer_id"), "pelanggan"), "pareto_c")
    with st.container(key="card_comp"):
        card_title("Komposisi pelanggan", "ditampilkan sebagai komposisi saja")
        cust = df.drop_duplicates("customer_id")
        tabs = st.tabs(["Segmen", "Kelompok usia", "Gender", "Tier membership", "Wilayah"])
        specs = [("customer_segment", "Segmen"), ("age_band", "Kelompok usia"), ("customer_gender", "Gender"),
                 ("membership_tier", "Tier membership"), ("customer_region", "Wilayah pelanggan")]
        cust = cust.assign(age_band=pd.cut(cust.customer_age, [17, 24, 34, 44, 54, 64, 90],
                                           labels=["18–24", "25–34", "35–44", "45–54", "55–64", "65+"]).astype(str))
        dfa = df.assign(age_band=pd.cut(df.customer_age, [17, 24, 34, 44, 54, 64, 90],
                                        labels=["18–24", "25–34", "35–44", "45–54", "55–64", "65+"]).astype(str))
        for tab, (col, lab) in zip(tabs, specs):
            with tab:
                cnt = cust[col].astype(str).value_counts()
                if col == "age_band":
                    cnt = cnt.reindex(["18–24", "25–34", "35–44", "45–54", "55–64", "65+"]).fillna(0)
                share = cnt / cnt.sum() * 100
                aov = dfa.groupby(dfa[col].astype(str)).net_sales.mean().reindex(cnt.index)
                spread = (aov.max() - aov.min()) / aov.mean() * 100
                a, b = st.columns([1.4, 1])
                with a:
                    static_chart(C.hbar(cnt.index, share.values, cnt.index, fmt="pct", title_x="% pelanggan", title_y=lab,
                                        extra=[f"${nf(v, 2)}" for v in aov.values], extra_name="Rata-rata per transaksi",
                                        max_value=share.max()), f"comp_{col}")
                with b:
                    st.markdown("<p class='lbl'>Rata-rata nilai per transaksi</p>" + "<table class='tbl' style='min-width:0'>" +
                                "".join(f"<tr><td>{html.escape(i)}</td><td class='num'><b>${nf(v, 2)}</b></td></tr>" for i, v in aov.items())
                                + "</table>", unsafe_allow_html=True)
                    note(f"Selisih antar {lab.lower()} hanya <b>{nf(spread, 1)}%</b> — tidak ada perbedaan perilaku belanja "
                         "yang berarti, jadi ini <b>bukan insight</b>, hanya gambaran komposisi.")

# ======================================================================= 5. Toko & wilayah
elif page == "Toko & wilayah":
    stt = M.store_table(df)
    with st.container(key="row_s1"):
        c1, c2 = st.columns(2)
        with c1, st.container(key="card_region"):
            rg = M.agg(df, "store_region")
            nst = df.groupby("store_region", observed=True).store_id.nunique()
            card_title("Penjualan per wilayah toko", "perbedaan terutama karena jumlah toko di tiap wilayah")
            howto("Klik wilayah untuk rinciannya.")
            clickable(C.hbar(rg.store_region.astype(str), rg.revenue, rg.store_region.astype(str),
                             title_x="Penjualan bersih (US$)", title_y="Wilayah",
                             extra=[f"{nst[r]} toko · ${nf(v / nst[r] / 1e3, 1)} rb per toko" for r, v in zip(rg.store_region, rg.revenue)],
                             extra_name="Toko"), "region", "group", {"col": "store_region"})
        with c2, st.container(key="card_stype"):
            ty = M.agg(df, "store_type")
            nty = df.groupby("store_type", observed=True).store_id.nunique()
            card_title("Penjualan per tipe toko", "klik tipe toko untuk rinciannya")
            clickable(C.hbar(ty.store_type.astype(str), ty.revenue, ty.store_type.astype(str),
                             title_x="Penjualan bersih (US$)", title_y="Tipe toko",
                             extra=[f"{nty[t]} toko · margin {nf(m, 1)}%" for t, m in zip(ty.store_type, ty.margin)],
                             extra_name="Info"), "stype", "group", {"col": "store_type"})
    with st.container(key="row_s2"):
        c1, c2 = st.columns([1, 1.6])
        with c1, st.container(key="card_sdist"):
            ratio = stt.revenue.max() / stt.revenue.min()
            card_title("Sebaran penjualan per toko", f"toko terbesar hanya <b>{nf(ratio, 1)}×</b> toko terkecil — kinerja toko sangat merata")
            static_chart(C.histogram(stt.revenue, title_x="Penjualan bersih per toko (US$)", title_y="Jumlah toko",
                                     bins=16, prefix="$"), "sdist")
        with c2, st.container(key="card_stbl"):
            card_title("Peringkat toko", "klik baris untuk detail toko · gunakan ikon kaca pembesar untuk mencari")
            show = stt[["rank", "store_id", "store_type", "region", "city", "revenue", "profit", "margin", "rows"]].rename(columns={
                "rank": "#", "store_id": "Toko", "store_type": "Tipe", "region": "Wilayah", "city": "Kota",
                "revenue": "Penjualan (US$)", "profit": "Laba (US$)", "margin": "Margin (%)", "rows": "Transaksi"})
            table_click(show, "stbl", "store", "Toko", height=380, column_config={
                "Penjualan (US$)": st.column_config.ProgressColumn(min_value=0, max_value=float(stt.revenue.max()), format="$%.0f"),
                "Laba (US$)": st.column_config.NumberColumn(format="$%.0f"),
                "Margin (%)": st.column_config.NumberColumn(format="%.1f%%")})

# ======================================================================= 6. Pemasok & operasional
elif page == "Pemasok & operasional":
    sp = M.supplier_table(df)
    with st.container(key="row_o1"):
        c1, c2 = st.columns([1.5, 1])
        with c1, st.container(key="card_supp"):
            card_title("Scorecard pemasok", f"{len(sp)} pemasok · skor 0–100 = 45% tepat waktu + 35% cacat rendah + 20% lead time pendek")
            howto("Klik gelembung untuk detail pemasok.")
            clickable(C.supplier_scatter(sp), "supp", "supplier")
        with c2, st.container(key="card_supptbl"):
            card_title("Peringkat pemasok", "klik baris untuk detail")
            show = sp[["supplier_id", "supplier_type", "score", "ontime", "defect", "lead"]].rename(columns={
                "supplier_id": "Pemasok", "supplier_type": "Tipe", "score": "Skor", "ontime": "Tepat waktu",
                "defect": "Cacat", "lead": "Lead time (hari)"})
            show["Tepat waktu"] *= 100
            show["Cacat"] *= 100
            table_click(show, "supptbl", "supplier", "Pemasok", height=420, column_config={
                "Skor": st.column_config.ProgressColumn(min_value=0, max_value=100, format="%.0f"),
                "Tepat waktu": st.column_config.NumberColumn(format="%.1f%%"),
                "Cacat": st.column_config.NumberColumn(format="%.2f%%"),
                "Lead time (hari)": st.column_config.NumberColumn(format="%.1f")})
    with st.container(key="row_o2"):
        c1, c2, c3 = st.columns(3)
        with c1, st.container(key="card_deliv"):
            dv = df.delivery_status.astype(str).value_counts(normalize=True) * 100
            card_title("Status pengiriman", f"<b>{nf(dv.get('Delivered', 0), 1)}%</b> terkirim")
            static_chart(C.hbar(dv.index, dv.values, dv.index, fmt="pct", title_x="% pengiriman", title_y="Status",
                                max_value=dv.max(), color=[C.GREEN if i == "Delivered" else C.PURPLE_L for i in dv.index]), "deliv")
        with c2, st.container(key="card_ret"):
            rr = df.return_reason.astype(str).replace({"nan": None}).dropna().value_counts()
            rr = rr[rr.index != "None"]
            card_title("Alasan retur", f"tingkat retur {nf((df.return_flag.astype(str) == 'Yes').mean() * 100, 1)}% · komposisi saja")
            static_chart(C.hbar(rr.index, rr.values, rr.index, fmt="num", title_x="Jumlah retur", title_y="Alasan",
                                max_value=rr.max(), color=C.PURPLE_L), "ret")
        with c3, st.container(key="card_cmp"):
            cc = df.complaint_category.astype(str).value_counts()
            cc = cc[~cc.index.isin(["None", "nan"])]
            card_title("Kategori keluhan", f"tingkat keluhan {nf((df.complaint_flag.astype(str) == 'Yes').mean() * 100, 1)}% · komposisi saja")
            static_chart(C.hbar(cc.index, cc.values, cc.index, fmt="num", title_x="Jumlah keluhan", title_y="Kategori",
                                max_value=cc.max(), color=C.PURPLE_L), "cmpl")
    note("Retur, keluhan, kepuasan, dan waktu antre di dataset ini tersebar acak (tidak berhubungan dengan toko, produk, "
         "maupun pemasok), sehingga hanya ditampilkan komposisinya. Lihat halaman <b>Kualitas data</b>.")

# ======================================================================= 7. Kualitas data
elif page == "Kualitas data":
    s = report["summary"]
    with st.container(key="card_qsum"):
        card_title("Ringkasan pembersihan data")
        st.markdown(mini([
            ("Baris mentah", nf(s["rows_raw"]), f"{s['cols_raw']} kolom"),
            ("Baris anomali dikeluarkan", nf(s["rows_removed"]), f"{nf(s['rows_removed'] / s['rows_raw'] * 100, 2)}%"),
            ("Baris dipakai dashboard", nf(s["rows_clean"]), f"{s['cols_kept']} kolom terpilih"),
            ("Periode", f"{pd.Timestamp(s['date_min']):%b %Y} – {pd.Timestamp(s['date_max']):%b %Y}", "2 tahun"),
        ]), unsafe_allow_html=True)
    def idn(t: str) -> str:
        return re.sub(r"(\d)\.(\d)", r"\1,\2", t)

    with st.container(key="card_qhow"):
        card_title("Bagaimana dashboard menyikapinya")
        st.markdown("""<div class="mini" style="grid-template-columns:repeat(auto-fit,minmax(min(100%,210px),1fr))">
<div class="mbox"><div class="l"><span class="status ok">✓ Dipakai sebagai insight</span></div><div class="s" style="font-size:.8rem;margin-top:.5rem">Penjualan, laba, diskon, margin kategori, konsentrasi produk & pelanggan, frekuensi & jam belanja, scorecard pemasok.</div></div>
<div class="mbox"><div class="l"><span class="status warn">! Hanya komposisi</span></div><div class="s" style="font-size:.8rem;margin-top:.5rem">Segmen, usia, gender, tier membership, wilayah pelanggan, retur, keluhan — tidak ada perbedaan perilaku berarti.</div></div>
<div class="mbox"><div class="l"><span class="status bad">✕ Tidak dipakai</span></div><div class="s" style="font-size:.8rem;margin-top:.5rem">Keranjang belanja (basket_id), nama hari libur, koordinat toko, skor kepuasan & churn.</div></div>
<div class="mbox"><div class="l"><span class="status bad">✕ Dikeluarkan</span></div><div class="s" style="font-size:.8rem;margin-top:.5rem">790 baris dengan jumlah barang membengkak yang tidak cocok dengan nilai penjualan.</div></div>
</div>""", unsafe_allow_html=True)
        note("Pola yang sangat rata (tanpa musim/pertumbuhan) dan variabel layanan yang acak menunjukkan dataset ini kemungkinan "
             "besar <b>sintetis</b>. Insight di dashboard sah untuk data ini, tetapi perlu diuji ulang pada data riil.")
    with st.container(key="card_checks"):
        card_title("Hasil pemeriksaan", "hijau = lolos · kuning = perlu perhatian · merah = tidak dipakai sebagai insight")
        lab = {"ok": "✓ Lolos", "warn": "! Perhatian", "bad": "✕ Tidak dipakai"}
        st.markdown("<div class='tblwrap'><table class='tbl qtbl' style='min-width:820px'><tr><th>Area</th><th>Pemeriksaan</th>"
                    "<th>Hasil</th><th>Status</th><th>Keterangan</th></tr>" + "".join(
                        f"<tr><td style='white-space:nowrap'>{html.escape(c['area'])}</td><td><b>{html.escape(c['check'])}</b></td>"
                        f"<td>{html.escape(idn(c['result']))}</td>"
                        f"<td><span class='status {c['status']}'>{lab[c['status']]}</span></td>"
                        f"<td style='font-size:.8rem;color:#707EAE'>{html.escape(idn(c['note']))}</td></tr>"
                        for c in report["checks"]) + "</table></div>", unsafe_allow_html=True)

st.markdown('<p class="hint" style="margin-top:1.4rem">Margin = laba kotor ÷ penjualan bersih (tertimbang). Hubungan bersifat '
            'korelasional, bukan sebab-akibat. Arahkan kursor ke grafik untuk tombol unduh PNG.</p>', unsafe_allow_html=True)


# ======================================================================= dialog detail
def _cd(point: dict) -> list:
    cd = point.get("customdata")
    if isinstance(cd, dict):
        return [cd[k] for k in sorted(cd, key=int)]
    return cd if isinstance(cd, list) else [cd]


def group_detail(sub: pd.DataFrame, subtitle: str, show_cat: bool = True):
    st.caption(subtitle)
    if sub.empty:
        st.info("Tidak ada transaksi.")
        return
    k = M.kpis(sub)
    st.markdown(mini([
        ("Penjualan bersih", money(k["revenue"]), f"{nf(k['revenue'] / K['revenue'] * 100, 1)}% dari tampilan"),
        ("Laba kotor", money(k["profit"]), f"margin {nf(k['margin'], 1)}% {badge(k['margin'] - K['margin'], 1, ' pp')}"),
        ("Transaksi", nf(k["tx"]), f"{nf(k['customers'])} pelanggan"),
        ("Rata-rata per transaksi", f"${nf(k['aov'], 2)}", badge((k['aov'] / K['aov'] - 1) * 100, 1) + " vs tampilan"),
    ]), unsafe_allow_html=True)
    if sub.month.nunique() > 2:
        st.plotly_chart(C.mini_trend(M.by_period(sub, "month"), "month"), config=C.CONFIG, key="dlg_trend")
    if show_cat:
        cat = M.agg(sub, "product_category").head(8)
        st.markdown("**Kategori terlaris di kelompok ini**")
        st.plotly_chart(C.hbar(cat.product_category.astype(str), cat.revenue, cat.product_category.astype(str),
                               title_x="Penjualan bersih (US$)", title_y="Kategori",
                               extra=[f"{nf(m, 1)}%" for m in cat.margin], extra_name="Margin"),
                        config=C.CONFIG, key="dlg_cat")


def category_detail(name: str):
    sub = df[df.product_category.astype(str) == name]
    group_detail(sub, f"Departemen: {sub.product_department.astype(str).iloc[0] if len(sub) else '-'}", show_cat=False)
    if sub.empty:
        return
    a, b = st.columns(2)
    with a:
        sc = M.agg(sub, "product_subcategory").head(8)
        st.markdown("**Subkategori**")
        st.plotly_chart(C.hbar(sc.product_subcategory.astype(str), sc.revenue, sc.product_subcategory.astype(str),
                               title_x="Penjualan bersih (US$)", title_y="Subkategori",
                               extra=[f"{nf(m, 1)}%" for m in sc.margin], extra_name="Margin"), config=C.CONFIG, key="dlg_sub")
    with b:
        dt = M.discount_table(sub)
        st.markdown("**Margin menurut besar diskon**")
        st.plotly_chart(C.discount_margin(dt).update_layout(height=280, clickmode="none"), config=C.CONFIG, key="dlg_dm")
    tp = sub.groupby(["product_id", "product_name"], observed=True).agg(
        revenue=("net_sales", "sum"), profit=("gross_profit", "sum"), loss=("is_loss", "sum")).reset_index()
    tp["margin"] = tp.profit / tp.revenue * 100
    st.markdown("**Produk teratas**")
    st.dataframe(tp.sort_values("revenue", ascending=False).head(15).rename(columns={
        "product_id": "ID", "product_name": "Produk", "revenue": "Penjualan (US$)", "profit": "Laba (US$)",
        "loss": "Transaksi rugi", "margin": "Margin (%)"}), hide_index=True, height=260,
        column_config={"Penjualan (US$)": st.column_config.NumberColumn(format="$%.0f"),
                       "Laba (US$)": st.column_config.NumberColumn(format="$%.0f"),
                       "Margin (%)": st.column_config.NumberColumn(format="%.1f%%")})


def product_detail(pid: str):
    sub = df[(df.product_id.astype(str) == pid) | (df.product_name.astype(str) == pid)]
    if sub.empty:
        st.info("Produk tidak ditemukan di tampilan ini.")
        return
    r = sub.iloc[0]
    st.markdown(f"<div class='chips' style='display:flex;gap:6px;flex-wrap:wrap'>" + "".join(
        f"<span class='badge p'>{html.escape(str(x))}</span>" for x in
        [r.product_category, r.product_subcategory, r.brand, r.brand_type, r.product_segment]) + "</div>", unsafe_allow_html=True)
    k = M.kpis(sub)
    st.markdown(mini([
        ("Harga normal", f"${nf(r.regular_price, 2)}", f"biaya ${nf(r.unit_cost, 2)}"),
        ("Titik impas diskon", f"{nf(r.break_even_disc, 1)}%", "diskon di atas ini = rugi"),
        ("Penjualan bersih", money(k["revenue"]), f"{nf(k['units'])} unit · {nf(k['tx'])} transaksi"),
        ("Laba kotor", money(k["profit"]), f"margin {nf(k['margin'], 1)}%"),
    ]), unsafe_allow_html=True)
    lines = sub[["transaction_datetime", "store_id", "quantity", "discount_percent", "selling_price", "net_sales", "gross_profit"]] \
        .sort_values("transaction_datetime", ascending=False).rename(columns={
            "transaction_datetime": "Waktu", "store_id": "Toko", "quantity": "Jumlah", "discount_percent": "Diskon (%)",
            "selling_price": "Harga jual", "net_sales": "Penjualan", "gross_profit": "Laba"})
    st.markdown("**Riwayat transaksi**")
    st.dataframe(lines, hide_index=True, height=280, column_config={
        "Harga jual": st.column_config.NumberColumn(format="$%.2f"), "Penjualan": st.column_config.NumberColumn(format="$%.2f"),
        "Laba": st.column_config.NumberColumn(format="$%.2f")})


def store_detail(sid: str):
    sub = df[df.store_id.astype(str) == sid]
    if sub.empty:
        st.info("Toko tidak ditemukan di tampilan ini.")
        return
    r = sub.iloc[0]
    stt = M.store_table(df)
    rank = int(stt.loc[stt.store_id.astype(str) == sid, "rank"].iloc[0])
    st.markdown(" ".join(f"<span class='badge p'>{html.escape(str(x))}</span>" for x in
                         [r.store_type, f"Wilayah {r.store_region}", r.store_city, f"{nf(r.store_size_sqft)} sqft",
                          f"rating {nf(r.store_rating, 2)}", f"peringkat #{rank} dari {len(stt)}"]), unsafe_allow_html=True)
    group_detail(sub, "")


def supplier_detail(sid: str):
    sub = df[df.supplier_id.astype(str) == sid]
    sp = M.supplier_table(df)
    row = sp[sp.supplier_id.astype(str) == sid]
    if sub.empty or row.empty:
        st.info("Pemasok tidak ditemukan.")
        return
    r = row.iloc[0]
    rank = int((sp.score > r.score).sum()) + 1
    st.markdown(mini([
        ("Skor", f"{nf(r.score, 0)}/100", f"peringkat #{rank} dari {len(sp)}"),
        ("Tepat waktu", f"{nf(r.ontime * 100, 1)}%", f"rata-rata {nf(sp.ontime.mean() * 100, 1)}%"),
        ("Tingkat cacat", f"{nf(r.defect * 100, 2)}%", f"rata-rata {nf(sp.defect.mean() * 100, 2)}%"),
        ("Lead time", f"{nf(r.lead, 1)} hari", f"rata-rata {nf(sp.lead.mean(), 1)} hari"),
    ]), unsafe_allow_html=True)
    st.caption(f"Tipe {r.supplier_type} · wilayah {r.region} · rating {nf(r.rating, 2)}")
    group_detail(sub, "Produk yang dipasok pemasok ini")


def open_dialog(title: str, body, *args):
    st.dialog(title, width="large", on_dismiss=reset_selection)(body)(*args)


if clicks:
    kind, pt, ctx = clicks[0]
    cd = _cd(pt)
    key = str(cd[0])
    if kind == "period":
        ts = pd.Timestamp(key)
        if ctx["freq"] == "month":
            sub = df[df.month == ts]
            ttl = f"{MONTHS_ID[ts.month - 1]} {ts.year}"
        else:
            sub = df[df.week == ts]
            ttl = f"Minggu mulai {ts:%d/%m/%Y}"
        open_dialog(ttl, group_detail, sub, "Ringkasan periode terpilih.")
    elif kind == "dept":
        open_dialog(f"Departemen {key}", group_detail, df[df.product_department.astype(str) == key],
                    "Kategori di dalam departemen ini.")
    elif kind == "cat":
        open_dialog(f"Kategori {key}", category_detail, key)
    elif kind == "dayhour":
        d, h = key.split("|")
        open_dialog(f"{DAYS_ID[d]}, pukul {int(h):02d}.00–{int(h):02d}.59", group_detail,
                    df[(df.day_name.astype(str) == d) & (df.shopping_hour == int(h))], "Transaksi pada hari & jam ini.")
    elif kind == "disc":
        sub = df[df.disc_bin == key]
        open_dialog(f"Transaksi dengan diskon {key}", group_detail, sub,
                    f"{nf(sub.is_loss.mean() * 100, 1)}% transaksi di kelompok ini rugi.")
    elif kind == "promo":
        open_dialog(f"Promosi: {key}", group_detail, df[df.promotion_type.astype(str) == key], "Transaksi dengan jenis promosi ini.")
    elif kind == "freq":
        c = df.groupby("customer_id").size()
        ids = c[c >= 5].index if key == "5+" else c[c == int(key)].index
        open_dialog(f"Pelanggan yang belanja {key}×", group_detail, df[df.customer_id.isin(ids)],
                    f"{nf(len(ids))} pelanggan.")
    elif kind == "group":
        col = ctx["col"]
        open_dialog(f"{key}", group_detail, df[df[col].astype(str) == key], "Rincian kelompok terpilih.")
    elif kind == "product":
        open_dialog(f"Produk {key}", product_detail, key)
    elif kind == "store":
        open_dialog(f"Toko {key}", store_detail, key)
    elif kind == "supplier":
        open_dialog(f"Pemasok {key}", supplier_detail, key)


# ======================================================================= auto refresh
if REFRESH > 0:
    @st.fragment(run_every=REFRESH)
    def _watch():
        d, _ = load_data()
        sig = (len(d), round(float(d.net_sales.sum()), 2))
        if ss.get("_sig") is None:
            ss._sig = sig
        elif sig != ss._sig:
            ss._sig = sig
            st.rerun(scope="app")
    _watch()
