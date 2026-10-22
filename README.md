# PennyPilot

PennyPilot adalah aplikasi web lokal untuk mencatat, mengategorikan, dan menganalisis pengeluaran pribadi dari file CSV. Data disimpan di SQLite di komputer sendiri; tidak ada akun, cloud, koneksi bank, API key, atau model machine learning.

Tujuan proyek ini adalah mengubah ekspor CSV yang berantakan menjadi ringkasan arus kas yang bisa ditindaklanjuti: kategori otomatis, tren bulanan, anggaran, proyeksi akhir bulan, dan daftar pengeluaran yang perlu ditinjau dengan alasan yang transparan.

## Fitur utama

- **Impor CSV bertahap** — pilih delimiter/encoding, pratinjau 20 baris, petakan kolom, validasi per baris, dan ringkasan sebelum menyimpan.
- **Interpretasi nominal fleksibel** — nominal bertanda, nominal absolut + kolom tipe, atau semua baris sebagai pengeluaran.
- **Deteksi kandidat duplikat** — fingerprint tanggal + deskripsi ternormalisasi + nominal + tipe, baik di dalam file maupun terhadap database. Duplikat dilewati secara default dan bisa disertakan setelah ditinjau.
- **Kategorisasi deterministik** — kategori dari CSV, aturan kata kunci yang dapat diedit, fallback per tipe transaksi. Kategori manual dan CSV terlindungi dari kategorisasi ulang.
- **Dashboard bulanan** — pendapatan, pengeluaran, arus kas bersih, anggaran, proyeksi, tren enam bulan, kategori terbesar, dan pengeluaran tidak biasa.
- **Deteksi pengeluaran tidak biasa** — median + MAD dengan minimal 5 pembanding dalam 180 hari, tanpa machine learning.
- **Anggaran dan proyeksi** — anggaran total/per kategori per bulan, proyeksi linear akhir bulan, dan saran anggaran berbasis median tiga bulan lengkap.
- **Tambah, edit, dan ekspor** — tambah transaksi manual, filter transaksi, edit kategori/deskripsi/tanggal/nominal/tipe, hapus dengan konfirmasi, ekspor CSV hasil filter.
- **Local-first** — tidak ada telemetri atau permintaan jaringan keluar.

## Tangkapan layar

Belum ada gambar biner di repositori. Tempatkan screenshot di `docs/screenshots/` lalu aktifkan tautan di bawah ini.

<!--
![Dashboard PennyPilot](docs/screenshots/dashboard.png)
![Wizard impor CSV](docs/screenshots/import.png)
![Anggaran dan proyeksi](docs/screenshots/budgets.png)
-->

Rekomendasi file screenshot:

| Halaman | Nama file |
|---|---|
| Dashboard | `docs/screenshots/dashboard.png` |
| Impor CSV | `docs/screenshots/import.png` |
| Anggaran | `docs/screenshots/budgets.png` |
| Kategori & Aturan | `docs/screenshots/rules.png` |

## Teknologi

- Python 3.11+
- Streamlit untuk UI lokal
- pandas untuk operasi tabular
- Plotly untuk grafik
- SQLite melalui `sqlite3` bawaan Python
- pytest untuk tes, Ruff untuk linting opsional

Tidak ada FastAPI, Redis, Celery, Docker, ORM besar, layanan cloud, LLM, scikit-learn, atau TensorFlow.

## Menjalankan aplikasi

### 1. Siapkan environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[dev]"
```

macOS/Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e ".[dev]"
```

Alternatif tanpa aktivasi virtual environment (Windows):

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

Dengan `uv`:

```powershell
uv venv --python 3.11 .venv
uv pip install --python .venv\Scripts\python.exe -e ".[dev]"
```

### 2. Jalankan aplikasi

Dari root repositori:

```powershell
streamlit run pennypilot/app.py
```

Jika venv belum diaktifkan:

```powershell
.\.venv\Scripts\python.exe -m streamlit run pennypilot/app.py
```

Buka alamat lokal yang ditampilkan Streamlit, biasanya `http://localhost:8501`.

### 3. Muat data

Saat database kosong, dashboard menampilkan tombol **Muat dataset demo**. Dataset sintetis ada di `pennypilot/sample_data/sample_transactions.csv` dan mencakup April–Oktober 2026, termasuk contoh pengeluaran tidak biasa.

Untuk data sendiri, buka **Impor CSV**, unggah file, lalu ikuti wizard.

## Menjalankan tes

```powershell
pytest
```

atau:

```powershell
python -m pytest
```

Linting:

```powershell
ruff check .
```

Tes tidak membutuhkan internet, akun, atau file database pribadi. Tes integrasi memakai database SQLite sementara, dan tes UI memakai `streamlit.testing.v1.AppTest` dengan database di temporary directory.

## Format CSV

Kolom minimum: tanggal, deskripsi, nominal. Kolom tipe dan kategori opsional.

```csv
tanggal,deskripsi,nominal,tipe,kategori
2026-10-01,Gaji bulanan PT Nusantara,12500000,income,
2026-10-02,Kopi di kafe,-25000,expense,
2026-10-03,Belanja mingguan Indomaret,-185000,expense,
```

Contoh lain dengan nominal absolut dan kolom tipe:

```csv
date,description,amount,type
2026-10-01,Freelance project,2500000,income
2026-10-02,Grab to office,45000,expense
```

Yang didukung:

- Delimiter koma, titik koma, tab, atau pipa. Deteksi otomatis tersedia.
- Encoding UTF-8 (dengan/tanpa BOM), Windows-1252, dan Latin-1.
- Format tanggal ISO, `DD/MM/YYYY`, `MM/DD/YYYY`, `DD-MM-YYYY`, `MM-DD-YYYY`, `YYYY/MM/DD`, `DD.MM.YYYY`, `MM.DD.YYYY`, dan beberapa format nama bulan.
- Nominal seperti `1.234.567,89`, `1,234,567.89`, `Rp 1.234`, `(25.000)`, atau `-12500`.
- Batas 10 MB dan 50.000 baris per file.
- Baris tidak valid dilaporkan dengan nomor baris dan alasan; baris valid lainnya tetap dapat diimpor.

Tanggal yang ambigu (misalnya `01/02/2026`) harus dipetakan dengan format eksplisit sebelum impor. File asli tidak pernah diubah.

## Cara kerja analisis

### Kategorisasi

Urutan penentuan kategori:

1. Kategori dari CSV, jika dikenali.
2. Aturan kata kunci aktif. Pencocokan tidak peka huruf besar/kecil.
3. Fallback: `Lainnya` untuk pengeluaran, `Pendapatan` untuk pendapatan.

Jika beberapa aturan cocok, urutannya:

1. Kata kunci terpanjang (lebih spesifik).
2. Prioritas eksplisit terbesar.
3. ID aturan terkecil (deterministik).

Kategori manual tidak pernah ditimpa saat aturan diterapkan ulang. Kategori dari CSV juga dipertahankan.

### Deteksi pengeluaran tidak biasa

Hanya transaksi `expense` yang dievaluasi.

Untuk setiap transaksi:

1. Ambil transaksi pengeluaran kategori yang sama dalam **180 hari sebelum** tanggal transaksi. Transaksi yang dievaluasi tidak masuk baseline.
2. Jika pembanding kurang dari **5**, statusnya **Belum cukup data**, bukan normal.
3. Hitung median dan MAD (median absolute deviation).
4. Jika MAD > 0, ambang = `median + 3 × 1,4826 × MAD`.
5. Jika MAD = 0 dan median > 0, ambang fallback = `2,5 × median`.
6. Jika MAD dan median sama-sama 0, statusnya **tidak informatif**; tidak ada keputusan otomatis.

Setiap hasil menyertakan status, ambang, jumlah pembanding, median, MAD, dan alasan berbahasa Indonesia. Label “Pengeluaran tidak biasa” berarti nominal relatif menyimpang dari riwayat kategori, bukan tuduhan fraud atau kesalahan.

### Anggaran dan proyeksi

Untuk bulan berjalan:

```text
estimasi akhir bulan = pengeluaran sejauh ini / hari berjalan × jumlah hari bulan
```

- Hari berjalan minimal 1.
- Bulan lampau memakai total aktual final, bukan proyeksi.
- Bulan mendatang berstatus belum tersedia.
- Bulan berjalan tanpa pengeluaran berstatus belum tersedia.
- Anggaran kosong disimpan sebagai `None`, bukan nol.
- Anggaran nol tidak dihitung sebagai persentase dan tidak memicu pembagian nol.

Saran anggaran memakai median total kategori pada tiga bulan kalender lengkap terakhir yang memiliki data. Bulan tanpa pengeluaran kategori dihitung Rp0. Jika data kurang dari tiga bulan, saran tidak ditampilkan. Pengguna harus meninjau dan mengonfirmasi sebelum menyimpan.

## Database, cadangan, dan privasi

Lokasi default:

```text
~/.pennypilot/pennypilot.db
```

Di Windows, `~` biasanya berarti `C:\Users\<nama-pengguna>`.

Ubah lokasi dengan variabel lingkungan:

```powershell
$env:PENNYPILOT_DB_PATH = "D:\data\pennypilot.db"
streamlit run pennypilot/app.py
```

```bash
export PENNYPILOT_DB_PATH="$HOME/data/pennypilot.db"
streamlit run pennypilot/app.py
```

Halaman **Pengaturan & Tentang** menyediakan tombol unduh snapshot `.db` yang konsisten. Untuk cadangan manual, hentikan aplikasi terlebih dahulu lalu salin file database:

```powershell
copy "$HOME\.pennypilot\pennypilot.db" "cadangan-pennypilot.db"
```

```bash
cp ~/.pennypilot/pennypilot.db cadangan-pennypilot.db
```

Menghapus database lokal:

```powershell
Remove-Item "$HOME\.pennypilot\pennypilot.db"
```

```bash
rm ~/.pennypilot/pennypilot.db
```

Catatan privasi:

- Semua data finansial disimpan lokal.
- Tidak ada telemetri, unggahan, atau permintaan jaringan keluar saat aplikasi digunakan.
- `.db`, file CSV pribadi, cache, dan secret diabaikan oleh `.gitignore`.
- Keamanan data bergantung pada keamanan perangkat dan akun pengguna.
- Aplikasi tidak memiliki autentikasi. Jangan mengeksposnya ke internet tanpa perlindungan tambahan.

## Struktur proyek

```text
pennypilot/
  __init__.py
  app.py                  # entry point Streamlit dan navigasi
  config.py               # batas impor, kategori, aturan default
  db.py                   # skema SQLite dan repository
  models.py               # dataclass domain
  utils.py                # Rupiah, parsing tanggal/nominal, fingerprint
  services/
    csv_import.py         # parsing, mapping, validasi, duplikat, impor
    categorizer.py        # aturan kata kunci dan kategorisasi ulang
    analytics.py          # KPI, tren, kategori, perbandingan anggaran
    anomalies.py          # median/MAD dan deteksi outlier
    budgets.py            # proyeksi dan saran anggaran
    exports.py            # ekspor CSV yang aman
  ui/
    common.py             # komponen dan CSS bersama
    dashboard.py
    transactions.py
    import_page.py
    budgets_page.py
    rules_page.py
    settings_page.py
  sample_data/
    sample_transactions.csv
tests/
  test_csv_import.py
  test_categorizer.py
  test_anomalies.py
  test_budgets.py
  test_analytics.py
  test_db.py
  test_exports.py
  test_app_smoke.py
docs/screenshots/         # tempat screenshot (belum berisi gambar)
.github/workflows/tests.yml
pyproject.toml
.gitignore
LICENSE
README.md
```

## Keputusan desain penting

- **Nominal non-negatif + tipe transaksi.** Semua jalur impor dinormalisasi ke `amount >= 0` dan `transaction_type` (`expense`/`income`) sebelum disimpan.
- **Fingerprint bukan unique constraint.** Dua pembelian identik bisa sah. Duplikat adalah kandidat yang ditinjau, bukan larangan.
- **Logika inti terpisah dari UI.** Service menerima DataFrame atau koneksi dan dapat diuji tanpa Streamlit.
- **Deterministik dan dapat dijelaskan.** Tidak ada model ML; aturan kategori dan deteksi anomali bisa direproduksi dari data yang sama.
- **SQLite sebagai sumber kebenaran.** Dashboard selalu menghitung dari database, bukan dari state sementara UI.
- **Penulisan dalam transaksi.** Impor, edit, hapus, dan penyimpanan anggaran memakai transaksi database dan query berparameter.

## Batasan MVP

- Satu pengguna, satu database lokal, satu mata uang (Rupiah).
- Tidak ada koneksi bank, e-wallet, OCR struk, sinkronisasi cloud, atau aplikasi mobile.
- Deteksi anomali hanya membandingkan nominal dalam kategori yang sama dan tidak memahami konteks (misalnya belanja tahunan).
- Kategori bawaan tetap; belum ada kategori kustom.
- Nominal disimpan sebagai `REAL` dan dibulatkan ke dua desimal. Toleransi pembulatan kecil dapat muncul pada agregasi pecahan.
- Belum ada autentikasi atau enkripsi database.
- Saran anggaran adalah median historis, bukan rekomendasi finansial personal.

## Roadmap

- Preset impor per bank/e-wallet dan penyimpanan pemetaan kolom.
- Kategori kustom dan tag.
- Transaksi berulang dan deteksi langganan.
- Laporan bulanan yang dapat diunduh (PDF/HTML).
- Multi-mata uang dengan kurs manual.
- Pencarian lanjutan dan penyimpanan filter.
- Enkripsi database opsional.

## Lisensi

MIT. Lihat [LICENSE](LICENSE).
