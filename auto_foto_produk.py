"""
Script untuk otomatis mengunduh foto produk UMKM Kendari
menggunakan koleksi gambar dari Pexels & Wikimedia Commons (public domain).

Tidak memerlukan API key - langsung unduh dari URL statis per kategori/jenis produk.
"""

import sqlite3
import os
import time
import urllib.request
import re
import random

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_PATH = os.path.join(BASE_DIR, "umkm_kendari.db")
UPLOAD_DIR = os.path.join(BASE_DIR, "static", "uploads")

# ============================================================
# Koleksi URL gambar per jenis produk
# Sumber: Pexels (pexels.com) & Wikimedia Commons - bebas pakai
# ============================================================

FOTO_DB = {
    # ===== KULINER =====
    "kopi": [
        "https://images.pexels.com/photos/302899/pexels-photo-302899.jpeg?w=400",
        "https://images.pexels.com/photos/374757/pexels-photo-374757.jpeg?w=400",
        "https://images.pexels.com/photos/585753/pexels-photo-585753.jpeg?w=400",
        "https://images.pexels.com/photos/1233528/pexels-photo-1233528.jpeg?w=400",
    ],
    "espresso": [
        "https://images.pexels.com/photos/312418/pexels-photo-312418.jpeg?w=400",
        "https://images.pexels.com/photos/350478/pexels-photo-350478.jpeg?w=400",
    ],
    "latte": [
        "https://images.pexels.com/photos/4109743/pexels-photo-4109743.jpeg?w=400",
        "https://images.pexels.com/photos/851555/pexels-photo-851555.jpeg?w=400",
    ],
    "cappucino": [
        "https://images.pexels.com/photos/374885/pexels-photo-374885.jpeg?w=400",
        "https://images.pexels.com/photos/1307658/pexels-photo-1307658.jpeg?w=400",
    ],
    "nasi": [
        "https://images.pexels.com/photos/1633578/pexels-photo-1633578.jpeg?w=400",
        "https://images.pexels.com/photos/1410235/pexels-photo-1410235.jpeg?w=400",
        "https://images.pexels.com/photos/699953/pexels-photo-699953.jpeg?w=400",
    ],
    "mie": [
        "https://images.pexels.com/photos/1279330/pexels-photo-1279330.jpeg?w=400",
        "https://images.pexels.com/photos/2347311/pexels-photo-2347311.jpeg?w=400",
    ],
    "bakso": [
        "https://images.pexels.com/photos/1726302/pexels-photo-1726302.jpeg?w=400",
        "https://images.pexels.com/photos/539451/pexels-photo-539451.jpeg?w=400",
    ],
    "bubur": [
        "https://images.pexels.com/photos/1987581/pexels-photo-1987581.jpeg?w=400",
        "https://images.pexels.com/photos/3026804/pexels-photo-3026804.jpeg?w=400",
    ],
    "kue": [
        "https://images.pexels.com/photos/291528/pexels-photo-291528.jpeg?w=400",
        "https://images.pexels.com/photos/1126359/pexels-photo-1126359.jpeg?w=400",
    ],
    "brownies": [
        "https://images.pexels.com/photos/45202/brownie-dessert-cake-sweet-45202.jpeg?w=400",
        "https://images.pexels.com/photos/3026808/pexels-photo-3026808.jpeg?w=400",
    ],
    "pisang": [
        "https://images.pexels.com/photos/1153655/pexels-photo-1153655.jpeg?w=400",
        "https://images.pexels.com/photos/2872755/pexels-photo-2872755.jpeg?w=400",
    ],
    "es": [
        "https://images.pexels.com/photos/1099680/pexels-photo-1099680.jpeg?w=400",
        "https://images.pexels.com/photos/3407777/pexels-photo-3407777.jpeg?w=400",
    ],
    "sambal": [
        "https://images.pexels.com/photos/9609836/pexels-photo-9609836.jpeg?w=400",
        "https://images.pexels.com/photos/8477578/pexels-photo-8477578.jpeg?w=400",
    ],
    "tempe": [
        "https://images.pexels.com/photos/5560763/pexels-photo-5560763.jpeg?w=400",
        "https://images.pexels.com/photos/7765164/pexels-photo-7765164.jpeg?w=400",
    ],
    "ikan": [
        "https://images.pexels.com/photos/1109197/pexels-photo-1109197.jpeg?w=400",
        "https://images.pexels.com/photos/3655916/pexels-photo-3655916.jpeg?w=400",
    ],
    "madu": [
        "https://images.pexels.com/photos/1006327/pexels-photo-1006327.jpeg?w=400",
        "https://images.pexels.com/photos/7689734/pexels-photo-7689734.jpeg?w=400",
    ],
    "abon": [
        "https://images.pexels.com/photos/8753720/pexels-photo-8753720.jpeg?w=400",
        "https://images.pexels.com/photos/6941021/pexels-photo-6941021.jpeg?w=400",
    ],
    "sagu": [
        "https://images.pexels.com/photos/1640777/pexels-photo-1640777.jpeg?w=400",
        "https://images.pexels.com/photos/5560682/pexels-photo-5560682.jpeg?w=400",
    ],
    "kasoami": [
        "https://images.pexels.com/photos/1640777/pexels-photo-1640777.jpeg?w=400",
        "https://images.pexels.com/photos/1279330/pexels-photo-1279330.jpeg?w=400",
    ],
    "lapa": [
        "https://images.pexels.com/photos/4110101/pexels-photo-4110101.jpeg?w=400",
        "https://images.pexels.com/photos/7625056/pexels-photo-7625056.jpeg?w=400",
    ],
    "sinonggi": [
        "https://images.pexels.com/photos/1640772/pexels-photo-1640772.jpeg?w=400",
        "https://images.pexels.com/photos/1640777/pexels-photo-1640777.jpeg?w=400",
    ],

    # ===== FASHION =====
    "sarung": [
        "https://images.pexels.com/photos/3622608/pexels-photo-3622608.jpeg?w=400",
        "https://images.pexels.com/photos/3622610/pexels-photo-3622610.jpeg?w=400",
    ],
    "tenun": [
        "https://images.pexels.com/photos/6850478/pexels-photo-6850478.jpeg?w=400",
        "https://images.pexels.com/photos/5624234/pexels-photo-5624234.jpeg?w=400",
    ],
    "batik": [
        "https://images.pexels.com/photos/6850565/pexels-photo-6850565.jpeg?w=400",
        "https://images.pexels.com/photos/3622608/pexels-photo-3622608.jpeg?w=400",
    ],
    "baju": [
        "https://images.pexels.com/photos/996329/pexels-photo-996329.jpeg?w=400",
        "https://images.pexels.com/photos/1536619/pexels-photo-1536619.jpeg?w=400",
    ],
    "kaos": [
        "https://images.pexels.com/photos/428340/pexels-photo-428340.jpeg?w=400",
        "https://images.pexels.com/photos/5384423/pexels-photo-5384423.jpeg?w=400",
    ],
    "topi": [
        "https://images.pexels.com/photos/1124465/pexels-photo-1124465.jpeg?w=400",
        "https://images.pexels.com/photos/2281897/pexels-photo-2281897.jpeg?w=400",
    ],
    "kemeja": [
        "https://images.pexels.com/photos/1598507/pexels-photo-1598507.jpeg?w=400",
        "https://images.pexels.com/photos/1038000/pexels-photo-1038000.jpeg?w=400",
    ],

    # ===== KRIYA =====
    "anyaman": [
        "https://images.pexels.com/photos/5410396/pexels-photo-5410396.jpeg?w=400",
        "https://images.pexels.com/photos/5858245/pexels-photo-5858245.jpeg?w=400",
    ],
    "rotan": [
        "https://images.pexels.com/photos/4207793/pexels-photo-4207793.jpeg?w=400",
        "https://images.pexels.com/photos/5410396/pexels-photo-5410396.jpeg?w=400",
    ],
    "gelang": [
        "https://images.pexels.com/photos/1191531/pexels-photo-1191531.jpeg?w=400",
        "https://images.pexels.com/photos/248077/pexels-photo-248077.jpeg?w=400",
    ],
    "perak": [
        "https://images.pexels.com/photos/1191531/pexels-photo-1191531.jpeg?w=400",
        "https://images.pexels.com/photos/3735641/pexels-photo-3735641.jpeg?w=400",
    ],
    "miniatur": [
        "https://images.pexels.com/photos/4919880/pexels-photo-4919880.jpeg?w=400",
        "https://images.pexels.com/photos/1082531/pexels-photo-1082531.jpeg?w=400",
    ],
    "tas": [
        "https://images.pexels.com/photos/1152077/pexels-photo-1152077.jpeg?w=400",
        "https://images.pexels.com/photos/1038000/pexels-photo-1038000.jpeg?w=400",
    ],
    "ukiran": [
        "https://images.pexels.com/photos/3768145/pexels-photo-3768145.jpeg?w=400",
        "https://images.pexels.com/photos/3768195/pexels-photo-3768195.jpeg?w=400",
    ],
    "kerajinan": [
        "https://images.pexels.com/photos/5858245/pexels-photo-5858245.jpeg?w=400",
        "https://images.pexels.com/photos/5410396/pexels-photo-5410396.jpeg?w=400",
    ],
    "buket": [
        "https://images.pexels.com/photos/931177/pexels-photo-931177.jpeg?w=400",
        "https://images.pexels.com/photos/56866/garden-rose-red-pink-56866.jpeg?w=400",
    ],
    "bunga": [
        "https://images.pexels.com/photos/931177/pexels-photo-931177.jpeg?w=400",
        "https://images.pexels.com/photos/56866/garden-rose-red-pink-56866.jpeg?w=400",
    ],

    # ===== JASA =====
    "fotografi": [
        "https://images.pexels.com/photos/1983037/pexels-photo-1983037.jpeg?w=400",
        "https://images.pexels.com/photos/3379934/pexels-photo-3379934.jpeg?w=400",
    ],
    "catering": [
        "https://images.pexels.com/photos/587741/pexels-photo-587741.jpeg?w=400",
        "https://images.pexels.com/photos/1640773/pexels-photo-1640773.jpeg?w=400",
    ],
    "jahit": [
        "https://images.pexels.com/photos/3373736/pexels-photo-3373736.jpeg?w=400",
        "https://images.pexels.com/photos/7679720/pexels-photo-7679720.jpeg?w=400",
    ],
    "laundry": [
        "https://images.pexels.com/photos/2254154/pexels-photo-2254154.jpeg?w=400",
        "https://images.pexels.com/photos/4498136/pexels-photo-4498136.jpeg?w=400",
    ],
    "barbershop": [
        "https://images.pexels.com/photos/1805600/pexels-photo-1805600.jpeg?w=400",
        "https://images.pexels.com/photos/3998423/pexels-photo-3998423.jpeg?w=400",
    ],
    "bengkel": [
        "https://images.pexels.com/photos/4489765/pexels-photo-4489765.jpeg?w=400",
        "https://images.pexels.com/photos/3806288/pexels-photo-3806288.jpeg?w=400",
    ],
    "percetakan": [
        "https://images.pexels.com/photos/4792729/pexels-photo-4792729.jpeg?w=400",
        "https://images.pexels.com/photos/267350/pexels-photo-267350.jpeg?w=400",
    ],
    "diving": [
        "https://images.pexels.com/photos/1645028/pexels-photo-1645028.jpeg?w=400",
        "https://images.pexels.com/photos/3369525/pexels-photo-3369525.jpeg?w=400",
    ],
    "travel": [
        "https://images.pexels.com/photos/346885/pexels-photo-346885.jpeg?w=400",
        "https://images.pexels.com/photos/1051073/pexels-photo-1051073.jpeg?w=400",
    ],
    "wisata": [
        "https://images.pexels.com/photos/346885/pexels-photo-346885.jpeg?w=400",
        "https://images.pexels.com/photos/2166559/pexels-photo-2166559.jpeg?w=400",
    ],
    "cuci": [
        "https://images.pexels.com/photos/372810/pexels-photo-372810.jpeg?w=400",
        "https://images.pexels.com/photos/97079/pexels-photo-97079.jpeg?w=400",
    ],

    # ===== RETAIL =====
    "toko": [
        "https://images.pexels.com/photos/1005638/pexels-photo-1005638.jpeg?w=400",
        "https://images.pexels.com/photos/264636/pexels-photo-264636.jpeg?w=400",
    ],
    "sembako": [
        "https://images.pexels.com/photos/1508666/pexels-photo-1508666.jpeg?w=400",
        "https://images.pexels.com/photos/264636/pexels-photo-264636.jpeg?w=400",
    ],
    "gantungan": [
        "https://images.pexels.com/photos/7319304/pexels-photo-7319304.jpeg?w=400",
        "https://images.pexels.com/photos/5849577/pexels-photo-5849577.jpeg?w=400",
    ],
    "oleh-oleh": [
        "https://images.pexels.com/photos/5849577/pexels-photo-5849577.jpeg?w=400",
        "https://images.pexels.com/photos/7319304/pexels-photo-7319304.jpeg?w=400",
    ],
    "bahan bangunan": [
        "https://images.pexels.com/photos/1249611/pexels-photo-1249611.jpeg?w=400",
        "https://images.pexels.com/photos/585419/pexels-photo-585419.jpeg?w=400",
    ],

    # ===== AGRO =====
    "lada": [
        "https://images.pexels.com/photos/1340116/pexels-photo-1340116.jpeg?w=400",
        "https://images.pexels.com/photos/3681659/pexels-photo-3681659.jpeg?w=400",
    ],
    "kunyit": [
        "https://images.pexels.com/photos/4198029/pexels-photo-4198029.jpeg?w=400",
        "https://images.pexels.com/photos/6157049/pexels-photo-6157049.jpeg?w=400",
    ],
    "rendang": [
        "https://images.pexels.com/photos/6941021/pexels-photo-6941021.jpeg?w=400",
        "https://images.pexels.com/photos/4518614/pexels-photo-4518614.jpeg?w=400",
    ],
    "garam": [
        "https://images.pexels.com/photos/1192032/pexels-photo-1192032.jpeg?w=400",
        "https://images.pexels.com/photos/3735641/pexels-photo-3735641.jpeg?w=400",
    ],
    "beras": [
        "https://images.pexels.com/photos/1393382/pexels-photo-1393382.jpeg?w=400",
        "https://images.pexels.com/photos/4110101/pexels-photo-4110101.jpeg?w=400",
    ],
    "sayur": [
        "https://images.pexels.com/photos/1508666/pexels-photo-1508666.jpeg?w=400",
        "https://images.pexels.com/photos/2255935/pexels-photo-2255935.jpeg?w=400",
    ],
    "tanaman": [
        "https://images.pexels.com/photos/1084199/pexels-photo-1084199.jpeg?w=400",
        "https://images.pexels.com/photos/931177/pexels-photo-931177.jpeg?w=400",
    ],
    "pertanian": [
        "https://images.pexels.com/photos/2286895/pexels-photo-2286895.jpeg?w=400",
        "https://images.pexels.com/photos/1084199/pexels-photo-1084199.jpeg?w=400",
    ],
    "bawang": [
        "https://images.pexels.com/photos/3620631/pexels-photo-3620631.jpeg?w=400",
        "https://images.pexels.com/photos/6157049/pexels-photo-6157049.jpeg?w=400",
    ],
    "cabe": [
        "https://images.pexels.com/photos/2870675/pexels-photo-2870675.jpeg?w=400",
        "https://images.pexels.com/photos/4033324/pexels-photo-4033324.jpeg?w=400",
    ],
    "arang": [
        "https://images.pexels.com/photos/1339372/pexels-photo-1339372.jpeg?w=400",
        "https://images.pexels.com/photos/4611704/pexels-photo-4611704.jpeg?w=400",
    ],

    # ===== DIGITAL =====
    "desain": [
        "https://images.pexels.com/photos/196644/pexels-photo-196644.jpeg?w=400",
        "https://images.pexels.com/photos/3184306/pexels-photo-3184306.jpeg?w=400",
    ],
    "website": [
        "https://images.pexels.com/photos/1181244/pexels-photo-1181244.jpeg?w=400",
        "https://images.pexels.com/photos/196644/pexels-photo-196644.jpeg?w=400",
    ],
    "komputer": [
        "https://images.pexels.com/photos/1181675/pexels-photo-1181675.jpeg?w=400",
        "https://images.pexels.com/photos/374074/pexels-photo-374074.jpeg?w=400",
    ],
    "digital": [
        "https://images.pexels.com/photos/3861969/pexels-photo-3861969.jpeg?w=400",
        "https://images.pexels.com/photos/196644/pexels-photo-196644.jpeg?w=400",
    ],
    "pulsa": [
        "https://images.pexels.com/photos/1287142/pexels-photo-1287142.jpeg?w=400",
        "https://images.pexels.com/photos/699122/pexels-photo-699122.jpeg?w=400",
    ],
    "studio": [
        "https://images.pexels.com/photos/1983037/pexels-photo-1983037.jpeg?w=400",
        "https://images.pexels.com/photos/2747446/pexels-photo-2747446.jpeg?w=400",
    ],
    "radio": [
        "https://images.pexels.com/photos/164853/pexels-photo-164853.jpeg?w=400",
        "https://images.pexels.com/photos/1626481/pexels-photo-1626481.jpeg?w=400",
    ],
    "internet": [
        "https://images.pexels.com/photos/1181671/pexels-photo-1181671.jpeg?w=400",
        "https://images.pexels.com/photos/374074/pexels-photo-374074.jpeg?w=400",
    ],

    # ===== KESEHATAN =====
    "jahe": [
        "https://images.pexels.com/photos/4198031/pexels-photo-4198031.jpeg?w=400",
        "https://images.pexels.com/photos/4198029/pexels-photo-4198029.jpeg?w=400",
    ],
    "minyak kelapa": [
        "https://images.pexels.com/photos/725998/pexels-photo-725998.jpeg?w=400",
        "https://images.pexels.com/photos/7565440/pexels-photo-7565440.jpeg?w=400",
    ],
    "vco": [
        "https://images.pexels.com/photos/725998/pexels-photo-725998.jpeg?w=400",
        "https://images.pexels.com/photos/7565440/pexels-photo-7565440.jpeg?w=400",
    ],
    "jamu": [
        "https://images.pexels.com/photos/4198029/pexels-photo-4198029.jpeg?w=400",
        "https://images.pexels.com/photos/5938413/pexels-photo-5938413.jpeg?w=400",
    ],
    "lulur": [
        "https://images.pexels.com/photos/3985338/pexels-photo-3985338.jpeg?w=400",
        "https://images.pexels.com/photos/3875157/pexels-photo-3875157.jpeg?w=400",
    ],
    "apotek": [
        "https://images.pexels.com/photos/5726794/pexels-photo-5726794.jpeg?w=400",
        "https://images.pexels.com/photos/4021769/pexels-photo-4021769.jpeg?w=400",
    ],
    "obat": [
        "https://images.pexels.com/photos/5726794/pexels-photo-5726794.jpeg?w=400",
        "https://images.pexels.com/photos/360622/pexels-photo-360622.jpeg?w=400",
    ],
    "vitamin": [
        "https://images.pexels.com/photos/5726794/pexels-photo-5726794.jpeg?w=400",
        "https://images.pexels.com/photos/360622/pexels-photo-360622.jpeg?w=400",
    ],
    "kacamata": [
        "https://images.pexels.com/photos/701877/pexels-photo-701877.jpeg?w=400",
        "https://images.pexels.com/photos/4587955/pexels-photo-4587955.jpeg?w=400",
    ],
    "herbal": [
        "https://images.pexels.com/photos/5938413/pexels-photo-5938413.jpeg?w=400",
        "https://images.pexels.com/photos/4198029/pexels-photo-4198029.jpeg?w=400",
    ],
}

# Fallback per kategori
KATEGORI_FALLBACK = {
    "Kuliner":    [
        "https://images.pexels.com/photos/1640777/pexels-photo-1640777.jpeg?w=400",
        "https://images.pexels.com/photos/1640772/pexels-photo-1640772.jpeg?w=400",
        "https://images.pexels.com/photos/699953/pexels-photo-699953.jpeg?w=400",
    ],
    "Fashion":    [
        "https://images.pexels.com/photos/3622608/pexels-photo-3622608.jpeg?w=400",
        "https://images.pexels.com/photos/996329/pexels-photo-996329.jpeg?w=400",
    ],
    "Kriya":      [
        "https://images.pexels.com/photos/5858245/pexels-photo-5858245.jpeg?w=400",
        "https://images.pexels.com/photos/5410396/pexels-photo-5410396.jpeg?w=400",
    ],
    "Jasa":       [
        "https://images.pexels.com/photos/3184306/pexels-photo-3184306.jpeg?w=400",
        "https://images.pexels.com/photos/1181671/pexels-photo-1181671.jpeg?w=400",
    ],
    "Retail":     [
        "https://images.pexels.com/photos/1005638/pexels-photo-1005638.jpeg?w=400",
        "https://images.pexels.com/photos/264636/pexels-photo-264636.jpeg?w=400",
    ],
    "Agro":       [
        "https://images.pexels.com/photos/2286895/pexels-photo-2286895.jpeg?w=400",
        "https://images.pexels.com/photos/1508666/pexels-photo-1508666.jpeg?w=400",
    ],
    "Digital":    [
        "https://images.pexels.com/photos/1181244/pexels-photo-1181244.jpeg?w=400",
        "https://images.pexels.com/photos/374074/pexels-photo-374074.jpeg?w=400",
    ],
    "Kesehatan":  [
        "https://images.pexels.com/photos/5726794/pexels-photo-5726794.jpeg?w=400",
        "https://images.pexels.com/photos/4198029/pexels-photo-4198029.jpeg?w=400",
    ],
    "default":    [
        "https://images.pexels.com/photos/1640777/pexels-photo-1640777.jpeg?w=400",
    ],
}


def get_url(nama_produk: str, kategori: str) -> str:
    """Cari URL gambar yang paling relevan."""
    nama_lower = nama_produk.lower()
    for key, urls in FOTO_DB.items():
        if key in nama_lower:
            return random.choice(urls)
    # Fallback per kategori
    cat_urls = KATEGORI_FALLBACK.get(kategori, KATEGORI_FALLBACK["default"])
    return random.choice(cat_urls)


def download_image(url: str, save_path: str) -> bool:
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "image/webp,image/jpeg,image/*"
        })
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = resp.read()
            if len(data) < 2000:
                return False
            with open(save_path, "wb") as f:
                f.write(data)
        return True
    except Exception as e:
        print(f"    Error: {e}")
        return False


def run():
    os.makedirs(UPLOAD_DIR, exist_ok=True)

    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row

    rows = conn.execute("""
        SELECT p.id, p.nama, k.nama as kategori_nama
        FROM produk p
        LEFT JOIN kategori k ON p.kategori_id = k.id
        WHERE p.gambar = 'default.jpg'
        ORDER BY p.id
    """).fetchall()

    total = len(rows)
    print(f"=== Auto Foto Produk dari Pexels ===")
    print(f"Ditemukan {total} produk dengan gambar default.jpg\n")

    sukses = 0
    gagal = 0

    for i, row in enumerate(rows, 1):
        produk_id = row["id"]
        nama = row["nama"]
        kategori = row["kategori_nama"] or "default"

        url = get_url(nama, kategori)

        # Nama file unik
        ts = int(time.time() * 1000) % 9999999999
        slug = re.sub(r'[^a-z0-9]+', '_', nama.lower())[:25].strip('_')
        filename = f"{ts}_{slug}.jpg"
        save_path = os.path.join(UPLOAD_DIR, filename)

        print(f"[{i}/{total}] ID={produk_id} | {nama[:55]}")

        ok = download_image(url, save_path)

        if ok:
            conn.execute("UPDATE produk SET gambar = ? WHERE id = ?", (filename, produk_id))
            conn.commit()
            sukses += 1
            print(f"    OK -> {filename}")
        else:
            gagal += 1
            print(f"    GAGAL -> tetap default.jpg")

        # Delay pendek agar tidak overload
        time.sleep(0.5)

    conn.close()

    print(f"\n=== Selesai ===")
    print(f"  Berhasil : {sukses} produk")
    print(f"  Gagal    : {gagal} produk")
    print(f"\nFoto tersimpan di: {UPLOAD_DIR}")


if __name__ == "__main__":
    run()
