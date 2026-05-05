<div align="center">

<img src="https://capsule-render.vercel.app/api?type=waving&color=0:1a1a2e,50:16213e,100:0f3460&height=200&section=header&text=UMKM%20Kendari&fontSize=60&fontColor=e94560&fontAlignY=38&desc=Sistem%20Rekomendasi%20Bisnis%20Lokal%20Kota%20Kendari&descAlignY=58&descSize=16&descColor=a8b2d8" />

<br/>

<p align="center">
  <img src="https://img.shields.io/badge/🐍%20Python-3.10+-0f3460?style=for-the-badge&labelColor=16213e" />
  &nbsp;
  <img src="https://img.shields.io/badge/🌶️%20Flask-Web%20Framework-e94560?style=for-the-badge&labelColor=16213e" />
  &nbsp;
  <img src="https://img.shields.io/badge/🗄️%20SQLite-Database-533483?style=for-the-badge&labelColor=16213e" />
</p>

<p align="center">
  <img src="https://img.shields.io/badge/HTML5-44.9%25-E34F26?style=flat-square&logo=html5&logoColor=white" />
  <img src="https://img.shields.io/badge/Python-43.3%25-3776AB?style=flat-square&logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/CSS3-10.5%25-1572B6?style=flat-square&logo=css3&logoColor=white" />
  <img src="https://img.shields.io/badge/JavaScript-1.3%25-F7DF1E?style=flat-square&logo=javascript&logoColor=black" />
</p>

<br/>

</div>

---

<br/>

## 🌺 Tentang Proyek

<img align="right" width="300" src="https://raw.githubusercontent.com/Platane/snk/output/github-contribution-grid-snake-dark.svg" />

**UMKM Kendari Rec** adalah platform rekomendasi berbasis web yang mempertemukan masyarakat dengan pelaku usaha lokal terbaik di **Kota Kendari, Sulawesi Tenggara**.

Dengan memanfaatkan algoritma rekomendasi berbasis data, sistem ini membantu pengguna menemukan UMKM yang paling relevan dengan kebutuhan mereka — dari kuliner lokal hingga kerajinan tangan khas Sulawesi.

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

### 🔍 Smart Recommendation
Algoritma rekomendasi cerdas yang mempelajari preferensi pengguna dan menyajikan UMKM paling relevan secara personal.

</td>
<td width="50%">

### 🗂️ Direktori Lengkap
Database komprehensif berisi ratusan UMKM Kota Kendari, lengkap dengan informasi kontak dan kategori bisnis.

</td>
</tr>
<tr>
<td width="50%">

### 🌐 Antarmuka Responsif
UI yang bersih dan ramah pengguna, dapat diakses dari perangkat apa pun — desktop maupun mobile.

</td>
<td width="50%">

### ⚡ Lightweight & Fast
Dibangun dengan Flask dan SQLite, ringan namun powerful untuk kebutuhan sistem rekomendasi lokal.

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
 ┣ 📂 models             ← Skema & model data
 ┃
 ┣ 📂 recommendation     ← Engine algoritma rekomendasi
 ┃
 ┣ 📂 routes             ← Routing & endpoint API
 ┃
 ┣ 📂 static             ← CSS · JS · Gambar & aset statis
 ┃
 ┣ 📂 templates          ← Template HTML (Jinja2)
 ┃
 ┣ 🐍 app.py             ← Entry point utama Flask
 ┣ ⚙️  config.py          ← Konfigurasi lingkungan
 ┣ 🛠️  init_db.py         ← Setup & inisialisasi database
 ┣ 🗃️  umkm_kendari.db    ← Database SQLite
 ┗ 📄 requirements.txt   ← Daftar dependensi Python
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

### 4️⃣ &nbsp; Inisialisasi Database

```bash
python init_db.py
```

### 5️⃣ &nbsp; Jalankan Aplikasi

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
| 🖥️ **Backend** | `Python` · `Flask` | Server & logika aplikasi |
| 🧠 **AI/Rec Engine** | `Python` | Algoritma rekomendasi |
| 🗄️ **Database** | `SQLite` | Penyimpanan data UMKM |
| 🎨 **Frontend** | `HTML5` · `CSS3` · `JS` | Antarmuka pengguna |
| 📄 **Templating** | `Jinja2` | Render halaman dinamis |

</div>

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