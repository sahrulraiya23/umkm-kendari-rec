"""
Fix foto untuk 15 produk yang masih default.jpg menggunakan URL alternatif.
"""
import sqlite3, os, time, urllib.request, re, random

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_PATH = os.path.join(BASE_DIR, "umkm_kendari.db")
UPLOAD_DIR = os.path.join(BASE_DIR, "static", "uploads")

# URL alternatif yang sudah teruji
ALTERNATIF = {
    "anyaman": [
        "https://images.pexels.com/photos/1050244/pexels-photo-1050244.jpeg?w=400",
        "https://images.pexels.com/photos/6044266/pexels-photo-6044266.jpeg?w=400",
        "https://images.pexels.com/photos/4207909/pexels-photo-4207909.jpeg?w=400",
    ],
    "miniatur": [
        "https://images.pexels.com/photos/760710/pexels-photo-760710.jpeg?w=400",
        "https://images.pexels.com/photos/1070536/pexels-photo-1070536.jpeg?w=400",
    ],
    "tas": [
        "https://images.pexels.com/photos/1152077/pexels-photo-1152077.jpeg?w=400",
        "https://images.pexels.com/photos/1152075/pexels-photo-1152075.jpeg?w=400",
    ],
    "lada": [
        "https://images.pexels.com/photos/1340116/pexels-photo-1340116.jpeg?w=400",
        "https://images.pexels.com/photos/4021769/pexels-photo-4021769.jpeg?w=400",
    ],
    "laundry": [
        "https://images.pexels.com/photos/4498136/pexels-photo-4498136.jpeg?w=400",
        "https://images.pexels.com/photos/5591580/pexels-photo-5591580.jpeg?w=400",
        "https://images.pexels.com/photos/6195125/pexels-photo-6195125.jpeg?w=400",
    ],
    "mebel": [
        "https://images.pexels.com/photos/1350789/pexels-photo-1350789.jpeg?w=400",
        "https://images.pexels.com/photos/271816/pexels-photo-271816.jpeg?w=400",
        "https://images.pexels.com/photos/276583/pexels-photo-276583.jpeg?w=400",
    ],
    "kerajinan": [
        "https://images.pexels.com/photos/1050244/pexels-photo-1050244.jpeg?w=400",
        "https://images.pexels.com/photos/6044266/pexels-photo-6044266.jpeg?w=400",
        "https://images.pexels.com/photos/4207909/pexels-photo-4207909.jpeg?w=400",
    ],
    "sagu": [
        "https://images.pexels.com/photos/1640777/pexels-photo-1640777.jpeg?w=400",
        "https://images.pexels.com/photos/357756/pexels-photo-357756.jpeg?w=400",
    ],
    "kasoami": [
        "https://images.pexels.com/photos/1640777/pexels-photo-1640777.jpeg?w=400",
        "https://images.pexels.com/photos/357756/pexels-photo-357756.jpeg?w=400",
    ],
    "kerang": [
        "https://images.pexels.com/photos/1268558/pexels-photo-1268558.jpeg?w=400",
        "https://images.pexels.com/photos/3046637/pexels-photo-3046637.jpeg?w=400",
    ],
}

def get_url(nama):
    n = nama.lower()
    for key, urls in ALTERNATIF.items():
        if key in n:
            return random.choice(urls)
    # Fallback umum
    return "https://images.pexels.com/photos/1640777/pexels-photo-1640777.jpeg?w=400"

def download_image(url, save_path):
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "Accept": "image/jpeg,image/*"
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

    print(f"=== Fix Foto ({len(rows)} produk) ===\n")
    sukses = 0

    for i, row in enumerate(rows, 1):
        pid = row["id"]
        nama = row["nama"]
        url = get_url(nama)

        ts = int(time.time() * 1000) % 9999999999
        slug = re.sub(r'[^a-z0-9]+', '_', nama.lower())[:25].strip('_')
        filename = f"{ts}_{slug}.jpg"
        save_path = os.path.join(UPLOAD_DIR, filename)

        print(f"[{i}/{len(rows)}] {nama[:55]}")
        ok = download_image(url, save_path)

        if ok:
            conn.execute("UPDATE produk SET gambar = ? WHERE id = ?", (filename, pid))
            conn.commit()
            sukses += 1
            print(f"    OK -> {filename}")
        else:
            print(f"    GAGAL")

        time.sleep(0.4)

    conn.close()
    print(f"\nSelesai: {sukses}/{len(rows)} berhasil diperbaiki")

if __name__ == "__main__":
    run()
