# Dashboard Analitik Supermarket

Dashboard interaktif (Streamlit + Plotly) dari 120.000 transaksi supermarket (Jan 2023 – Des 2024,
200 toko, 5.000 produk, ~75 ribu pelanggan, 50 pemasok). Gaya visual terinspirasi template *Venus Dashboard*
(ThemeWagon): latar #F4F7FE, kartu putih radius 20px, aksen ungu #4318FF, font DM Sans.

## Struktur proyek

```
dashboard-supermarket/
├── app.py                       # 7 halaman, filter global, pop-up detail
├── src/
│   ├── data.py                  # Muat data (parquet / Supabase), kolom turunan, format angka
│   ├── metrics.py               # Agregasi, insight otomatis, simulasi batas diskon, scorecard
│   └── charts.py                # Grafik Plotly bergaya Venus
├── assets/style.css             # Tema visual
├── data/
│   ├── supermarket.parquet      # Data bersih: 119.210 baris × 58 kolom (~6 MB)
│   └── quality_report.json      # Hasil pemeriksaan kualitas data
├── scripts/prepare_data.py      # CSV mentah (206 MB) → parquet + laporan kualitas
├── .streamlit/config.toml
└── requirements.txt
```

## Halaman

| Halaman | Isi | Klik → pop-up |
|---|---|---|
| **Ringkasan** | 5 KPI · tren penjualan & laba (bulanan/mingguan) · porsi departemen · heatmap hari × jam · temuan otomatis | Bulan/minggu, departemen, sel jam |
| **Diskon & profitabilitas** | Margin per tingkat diskon · volume tidak naik · simulasi batas diskon · jenis promosi · kerugian per kategori | Tingkat diskon, promosi, baris kategori |
| **Produk & kategori** | Peta kategori (penjualan × margin) · kurva Pareto · daftar produk teratas/terbawah · tipe merek & segmen | Kategori, produk, tipe merek/segmen |
| **Pelanggan** | Frekuensi belanja · konsentrasi · komposisi (segmen, usia, gender, tier, wilayah) | Kelompok frekuensi |
| **Toko & wilayah** | Wilayah · tipe toko · sebaran penjualan per toko · peringkat 200 toko | Wilayah, tipe, toko |
| **Pemasok & operasional** | Scorecard 50 pemasok · status pengiriman · alasan retur · kategori keluhan | Pemasok |
| **Kualitas data** | 17 pemeriksaan + cara dashboard menyikapinya | – |

Filter global (tombol **Filter** kanan atas): periode, wilayah toko, tipe toko, departemen, segmen pelanggan.

## Insight utama
1. Margin turun dari 44,2% (tanpa diskon) ke 1,8% (diskon 31–50%), sementara barang per transaksi tetap ~8,5.
2. Jenis promosi (Bundle, BOGO, dll.) tidak berbeda dari tanpa promosi — yang menentukan hanya besar diskon.
3. 6,4% transaksi rugi (−$58,8 rb), semuanya karena diskon melewati titik impas.
4. Membatasi diskon maksimal 20% diperkirakan menambah laba ±$462 rb (+12%), dengan asumsi volume tetap.
5. Margin kategori 28,5% (Kidswear) – 42,9% (Supplements), ditentukan rasio biaya/harga.
6. 20% produk = 51% penjualan; 20% pelanggan = 54%; 58% pelanggan hanya belanja sekali.
7. 43% transaksi terjadi pukul 07.00–10.59.

## Catatan kualitas data
Dataset kemungkinan besar **sintetis**: penjualan bulanan hampir rata, dan variabel kepuasan/churn/loyalitas
tidak berhubungan dengan apa pun. 790 baris anomali (jumlah barang tidak cocok dengan nilai penjualan) dikeluarkan.
Variabel acak hanya ditampilkan komposisinya. Rincian di halaman **Kualitas data**.

## Jalankan lokal
```bash
pip install -r requirements.txt
streamlit run app.py
```
Untuk membuat ulang data dari CSV mentah:
```bash
python scripts/prepare_data.py path/ke/supermarket_large_dataset.csv
```

## Deploy gratis (Streamlit Community Cloud)
1. Buat repo GitHub `dashboard-supermarket`, upload semua isi folder ini (file `.parquet` ~6 MB aman diunggah lewat browser).
   Folder `.streamlit` dibuat lewat **Add file → Create new file** → `.streamlit/config.toml`.
2. share.streamlit.io → **Create app** → pilih repo, branch `main`, file `app.py`, Python 3.12 → **Deploy**.

## Data real-time (opsional)
Isi **Secrets** di Streamlit Cloud:
```toml
DATA_SOURCE = "supabase"
SUPABASE_URL = "https://xxxx.supabase.co"
SUPABASE_ANON_KEY = "sb_publishable_xxx"
SUPABASE_TABLE = "supermarket_sales"
CACHE_TTL_SECONDS = 60
AUTO_REFRESH_SECONDS = 60
```
Tabel Supabase harus memiliki kolom yang sama dengan `data/supermarket.parquet`.
