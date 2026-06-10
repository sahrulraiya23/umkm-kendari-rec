import sqlite3

conn = sqlite3.connect('umkm_kendari.db')
conn.row_factory = sqlite3.Row

total = conn.execute("SELECT COUNT(*) FROM produk WHERE gambar = 'default.jpg'").fetchone()[0]
print(f'Produk dengan default.jpg: {total}')

rows = conn.execute("SELECT id, nama, kategori_id FROM produk WHERE gambar = 'default.jpg' LIMIT 20").fetchall()
for r in rows:
    print(f"  ID={r['id']} | {r['nama'][:70]}")

conn.close()
