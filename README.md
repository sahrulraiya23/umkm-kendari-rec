<div align="center">

<img src="https://capsule-render.vercel.app/api?type=waving&color=0:1a1a2e,50:16213e,100:0f3460&height=200&section=header&text=UMKM%20Kendari&fontSize=60&fontColor=e94560&fontAlignY=38&desc=Sistem%20Rekomendasi%20Produk%20UMKM%20Kota%20Kendari&descAlignY=58&descSize=16&descColor=a8b2d8" />

<br/>

<p align="center">
  <img src="https://img.shields.io/badge/🐍%20Python-3.10+-0f3460?style=for-the-badge&labelColor=16213e" />
  &nbsp;
  <img src="https://img.shields.io/badge/🌶️%20Flask-3.1.0-e94560?style=for-the-badge&labelColor=16213e" />
  &nbsp;
  <img src="https://img.shields.io/badge/🗄️%20SQLite-Database-533483?style=for-the-badge&labelColor=16213e" />
</p>

<p align="center">
  <img src="https://img.shields.io/badge/HTML5-44.9%25-E34F26?style=flat-square&logo=html5&logoColor=white" />
  <img src="https://img.shields.io/badge/Python-43.3%25-3776AB?style=flat-square&logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/CSS3-10.5%25-1572B6?style=flat-square&logo=css3&logoColor=white" />
  <img src="https://img.shields.io/badge/JavaScript-1.3%25-F7DF1E?style=flat-square&logo=javascript&logoColor=black" />
</p>

<p align="center">
  <img src="https://img.shields.io/badge/TensorFlow-2.18.0-FF6F00?style=flat-square&logo=tensorflow&logoColor=white" />
  <img src="https://img.shields.io/badge/Gemini%20AI-0.8.3-4285F4?style=flat-square&logo=google&logoColor=white" />
  <img src="https://img.shields.io/badge/n8n-Automation-E03C2A?style=flat-square&logo=n8n&logoColor=white" />
  <img src="https://img.shields.io/badge/Google%20Sheets-Sync-34A853?style=flat-square&logo=googlesheets&logoColor=white" />
</p>

<br/>

</div>

---

<br/>

## 🌺 Tentang Proyek

<img align="right" width="300" src="https://raw.githubusercontent.com/Platane/snk/output/github-contribution-grid-snake-dark.svg" />

**UMKM Kendari Rec** adalah platform rekomendasi berbasis web yang mempertemukan masyarakat dengan pelaku usaha lokal terbaik di **Kota Kendari, Sulawesi Tenggara**.

Sistem ini menggabungkan dua algoritma rekomendasi:
- **KNN (K-Nearest Neighbor)** — untuk pengguna baru (*cold-start*)
- **NCF (Neural Collaborative Filtering)** — setelah pengguna memberikan rating

Dilengkapi dengan **chatbot AI (Gemini)**, **integrasi n8n**, dan **sinkronisasi otomatis ke Google Sheets**.

> *"Teknologi untuk memberdayakan ekonomi lokal Kendari."* 🏝️

<br/>
<br/>
<br/>

---

<br/>

## ✨ Fitur Unggulan

<table>
<tr>
<td width="50%">

### 🤖 Smart Recommendation (KNN + NCF)
Dua algoritma bekerja bersama: KNN untuk pengguna baru dan Neural Collaborative Filtering (deep learning) setelah cukup data rating terkumpul.

</td>
<td width="50%">

### 💬 Chatbot AI (Gemini)
Asisten virtual berbasis Google Gemini AI yang membantu pengguna menemukan produk UMKM melalui percakapan natural.

</td>
</tr>
<tr>
<td width="50%">

### 🔗 Integrasi n8n & WhatsApp
API endpoint khusus untuk n8n memungkinkan chatbot WhatsApp/Telegram, sinkronisasi terjadwal, dan notifikasi otomatis.

</td>
<td width="50%">

### 📊 Sinkronisasi Google Sheets
Data produk UMKM tersinkronisasi otomatis ke Google Sheets menggunakan Google Sheets API dan service account.

</td>
</tr>
<tr>
<td width="50%">

### 🏪 Multi-Role (Admin, Seller, User)
Tiga peran pengguna: Admin (kelola semua), Seller (kelola toko & produk), dan User (browse & rating).

</td>
<td width="50%">

### 🌐 Antarmuka Responsif
UI bersih dan ramah pengguna berbasis HTML5 + CSS3 + Jinja2, dapat diakses dari desktop maupun mobile.

</td>
</tr>
</table>

<br/>

---

<br/>

## 🗂️ Struktur Proyek

```
📦 umkm-kendari-rec
 ┃
 ┣ 📂 models/                  ← Skema & model data (database, user, produk, dll.)
 ┃
 ┣ 📂 recommendation/          ← Engine algoritma rekomendasi
 ┃   ┣ 📄 engine.py            ← Dispatcher KNN / NCF
 ┃   ┣ 📄 knn.py               ← Implementasi K-Nearest Neighbor
 ┃   ┣ 📄 ncf.py               ← Neural Collaborative Filtering (TensorFlow/Keras)
 ┃   ┣ 📄 evaluation.py        ← Evaluasi metrik rekomendasi
 ┃   ┗ 📂 saved_model/         ← Model NCF tersimpan (.keras)
 ┃
 ┣ 📂 routes/                  ← Routing & endpoint Flask
 ┃   ┣ 📄 auth.py              ← Login, register, logout
 ┃   ┣ 📄 main.py              ← Halaman utama & rekomendasi
 ┃   ┣ 📄 admin.py             ← Panel admin
 ┃   ┣ 📄 seller.py            ← Dasbor & manajemen produk seller
 ┃   ┣ 📄 api.py               ← REST API internal
 ┃   ┗ 📄 n8n_api.py           ← API endpoint khusus integrasi n8n
 ┃
 ┣ 📂 services/                ← Layanan eksternal (Gemini AI, GSheets)
 ┃
 ┣ 📂 static/                  ← CSS · JS · Gambar & aset statis
 ┃   ┗ 📂 uploads/             ← Foto produk (diabaikan Git, hanya .gitkeep)
 ┃
 ┣ 📂 templates/               ← Template HTML (Jinja2)
 ┃
 ┣ 🐍 app.py                   ← Entry point utama Flask
 ┣ ⚙️  config.py               ← Konfigurasi lingkungan & konstanta
 ┣ 🛠️  init_db.py              ← Setup & inisialisasi database SQLite
 ┣ 📥 import_csv.py            ← Import data dari CSV ke database
 ┣ 🔄 sync_csv_ke_gsheet.py    ← Sync CSV → Google Sheets
 ┣ 📊 eval_sistem_rekomendasi.py ← Script evaluasi algoritma
 ┣ 📄 requirements.txt         ← Daftar dependensi Python
 ┗ 🚫 .gitignore               ← File yang diabaikan Git
```

<br/>

---

<br/>

## 🚀 Instalasi & Menjalankan

### 1️⃣ &nbsp; Clone Repositori

```bash
git clone https://github.com/sahrulraiya23/umkm-kendari-rec.git
cd umkm-kendari-rec
```

### 2️⃣ &nbsp; Buat Virtual Environment

```bash
# Buat venv
python -m venv venv

# Aktifkan — Linux/macOS
source venv/bin/activate

# Aktifkan — Windows
venv\Scripts\activate
```

### 3️⃣ &nbsp; Install Dependensi

```bash
pip install -r requirements.txt
```

### 4️⃣ &nbsp; Konfigurasi Environment Variables

Buat file `.env` atau set variabel berikut di terminal:

```bash
# Windows (PowerShell)
$env:SECRET_KEY       = "ganti-dengan-secret-key-acak"
$env:GEMINI_API_KEY   = "AIza..."        # Dapatkan di aistudio.google.com/apikey
$env:GSHEET_SPREADSHEET_ID = "1BxiM..."  # ID dari URL Google Sheets
$env:N8N_API_KEY      = "key-rahasia-n8n"

# Linux / macOS
export SECRET_KEY="ganti-dengan-secret-key-acak"
export GEMINI_API_KEY="AIza..."
export GSHEET_SPREADSHEET_ID="1BxiM..."
export N8N_API_KEY="key-rahasia-n8n"
```

> **Catatan Google Sheets:** Letakkan file `service_account.json` (credential Google Cloud) di root proyek. **Jangan commit file ini ke Git!** (sudah masuk `.gitignore`)

### 5️⃣ &nbsp; Inisialisasi Database

```bash
python init_db.py
```

### 6️⃣ &nbsp; (Opsional) Import Data CSV

```bash
python import_csv.py
```

### 7️⃣ &nbsp; Jalankan Aplikasi

```bash
python app.py
```

### 🌐 &nbsp; Buka di Browser

```
http://localhost:5000
```

<br/>

---

<br/>

## 🛠️ Tech Stack

<div align="center">

| Layer | Teknologi | Peran |
|:---:|:---:|:---|
| 🖥️ **Backend** | `Python 3.10+` · `Flask 3.1` | Server & logika aplikasi |
| 🧠 **Rec Engine** | `scikit-learn` · `TensorFlow 2.18` · `Keras` | KNN & Neural Collaborative Filtering |
| 🤖 **AI Chatbot** | `Google Gemini AI` (`google-generativeai`) | Chatbot percakapan natural |
| 🗄️ **Database** | `SQLite` | Penyimpanan data UMKM, user, rating |
| 📊 **Spreadsheet** | `gspread` · `Google Sheets API` | Sinkronisasi data produk otomatis |
| 🔗 **Automation** | `n8n` REST API | WhatsApp/Telegram bot & workflow otomatis |
| 🎨 **Frontend** | `HTML5` · `CSS3` · `JavaScript` | Antarmuka pengguna |
| 📄 **Templating** | `Jinja2` | Render halaman dinamis |
| 🔐 **Auth** | `Flask-Login` · `Werkzeug` | Autentikasi & manajemen sesi |

</div>

<br/>

---

<br/>

## 🔌 API Endpoint (n8n Integration)

Semua endpoint `/n8n/*` memerlukan API Key via header atau query param.

**Autentikasi:**
```
Header:      Authorization: Bearer <N8N_API_KEY>
Query param: ?api_key=<N8N_API_KEY>
```

| Method | Endpoint | Deskripsi |
|:---:|:---|:---|
| `GET` | `/n8n/ping` | Health check (tanpa auth) |
| `GET` | `/n8n/produk` | Ambil semua produk (support: `?limit`, `?offset`, `?kategori`, `?tersedia`) |
| `GET` | `/n8n/produk/cari?q=keyword` | Cari produk berdasarkan keyword |
| `GET` | `/n8n/statistik` | Ringkasan statistik (total produk, UMKM, ulasan) |
| `POST` | `/n8n/chat` | Chatbot AI — body: `{"message": "...", "user_id": "..."}` |
| `POST` | `/n8n/sync-trigger` | Trigger sync & return data siap tulis ke Google Sheets |

<br/>

---

<br/>

## ⚙️ Konfigurasi Lanjutan

### Algoritma Rekomendasi

Edit di [`config.py`](config.py):

```python
NCF_MIN_RATINGS = 3    # Minimum rating sebelum beralih ke NCF
KNN_N_NEIGHBORS = 10   # Jumlah tetangga terdekat KNN
```

### Evaluasi Sistem

```bash
# Evaluasi metrik rekomendasi (Precision, Recall, NDCG, dll.)
python eval_sistem_rekomendasi.py

# Evaluasi tabel akademik
python eval_tabel_akademik.py
```

<br/>

---

<br/>

## 🤝 Cara Berkontribusi

Kami menyambut kontribusi dari siapa saja! Ikuti langkah berikut:

```bash
# 1. Fork dan clone repositori
git clone https://github.com/USERNAME/umkm-kendari-rec.git

# 2. Buat branch baru untuk fiturmu
git checkout -b feature/nama-fitur-kamu

# 3. Lakukan perubahan, lalu commit
git add .
git commit -m "✨ feat: deskripsi fitur singkat"

# 4. Push ke GitHub
git push origin feature/nama-fitur-kamu

# 5. Buka Pull Request di GitHub 🎉
```

<br/>

---

<br/>

<div align="center">

<img src="https://capsule-render.vercel.app/api?type=waving&color=0:0f3460,50:16213e,100:1a1a2e&height=120&section=footer" />

<br/>

**Dibuat dengan ❤️ untuk UMKM Kota Kendari**

*Sulawesi Tenggara · Indonesia* 🇮🇩

<br/>

[![GitHub](https://img.shields.io/badge/GitHub-sahrulraiya23-e94560?style=flat-square&logo=github)](https://github.com/sahrulraiya23)

<br/>

⭐ **Berikan bintang jika proyek ini membantu!** ⭐

</div>