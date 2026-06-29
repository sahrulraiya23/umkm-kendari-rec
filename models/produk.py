from models.database import get_db


class Produk:
    """Model Produk UMKM Kota Kendari."""

    def __init__(self, id, nama, deskripsi='', harga=0, stok=0, gambar='default.jpg',
                 kategori_id=None, seller_id=None, created_at=None, tersedia=1, kecamatan='Kendari', **kwargs):
        self.id = id
        self.nama = nama
        self.deskripsi = deskripsi
        self.harga = harga
        self.stok = stok
        self.tersedia = bool(tersedia)  # True = ada stok, False = habis
        self.gambar = gambar if gambar else 'default.jpg'
        self.kategori_id = kategori_id
        self.seller_id = seller_id
        self.created_at = created_at
        self.kecamatan = kecamatan
        # Extra fields dari JOIN
        self.kategori_nama = kwargs.get('kategori_nama', '')
        self.seller_nama = kwargs.get('seller_nama', '')
        self.seller_no_telepon = kwargs.get('seller_no_telepon', '')
        self.avg_rating = kwargs.get('avg_rating', 0)
        self.total_rating = kwargs.get('total_rating', 0)

    @staticmethod
    def _base_query():
        return '''
            SELECT p.*,
                   k.nama as kategori_nama,
                   u.nama_lengkap as seller_nama,
                   u.no_telepon as seller_no_telepon,
                   COALESCE(AVG(r.score), 0) as avg_rating,
                   COUNT(r.id) as total_rating
            FROM produk p
            LEFT JOIN kategori k ON p.kategori_id = k.id
            LEFT JOIN users u ON p.seller_id = u.id
            LEFT JOIN ratings r ON p.id = r.produk_id
        '''

    @staticmethod
    def get_all(limit=None, kecamatan=None):
        db = get_db()
        query = Produk._base_query()
        params = []

        if kecamatan:
            query += ' WHERE p.kecamatan = ?'
            params.append(kecamatan)

        query += ' GROUP BY p.id ORDER BY p.created_at DESC'

        if limit:
            query += f' LIMIT {limit}'

        rows = db.execute(query, params).fetchall()
        return [Produk(**dict(row)) for row in rows]

    @staticmethod
    def get_by_id(produk_id):
        db = get_db()
        query = Produk._base_query() + ' WHERE p.id = ? GROUP BY p.id'
        row = db.execute(query, (produk_id,)).fetchone()
        if row:
            return Produk(**dict(row))
        return None

    @staticmethod
    def get_by_kategori(kategori_id, limit=None):
        db = get_db()
        query = Produk._base_query() + ' WHERE p.kategori_id = ? GROUP BY p.id ORDER BY p.created_at DESC'
        if limit:
            query += f' LIMIT {limit}'
        rows = db.execute(query, (kategori_id,)).fetchall()
        return [Produk(**dict(row)) for row in rows]

    @staticmethod
    def get_by_kecamatan(kecamatan, limit=None):
        return Produk.get_all(limit=limit, kecamatan=kecamatan)

    @staticmethod
    def get_by_seller(seller_id, limit=None):
        """Mengambil semua produk dari seller tertentu."""
        db = get_db()
        query = Produk._base_query() + ' WHERE p.seller_id = ? GROUP BY p.id ORDER BY p.created_at DESC'
        if limit:
            query += f' LIMIT {limit}'
        rows = db.execute(query, (seller_id,)).fetchall()
        return [Produk(**dict(row)) for row in rows]

    @staticmethod
    def get_kecamatan_list():
        """Mengembalikan list semua kecamatan yang ada produknya."""
        db = get_db()
        rows = db.execute('SELECT DISTINCT kecamatan FROM produk ORDER BY kecamatan').fetchall()
        return [row['kecamatan'] for row in rows]

    @staticmethod
    def get_popular(limit=8):
        db = get_db()
        query = Produk._base_query() + ' GROUP BY p.id HAVING total_rating > 0 ORDER BY avg_rating DESC, total_rating DESC LIMIT ?'
        rows = db.execute(query, (limit,)).fetchall()
        return [Produk(**dict(row)) for row in rows]

    @staticmethod
    def get_trending(limit=8):
        db = get_db()
        query = Produk._base_query() + ' GROUP BY p.id ORDER BY total_rating DESC, avg_rating DESC LIMIT ?'
        rows = db.execute(query, (limit,)).fetchall()
        return [Produk(**dict(row)) for row in rows]

    @staticmethod
    def search(keyword, limit=20):
        db = get_db()
        query = Produk._base_query() + ' WHERE p.nama LIKE ? OR p.deskripsi LIKE ? GROUP BY p.id ORDER BY avg_rating DESC LIMIT ?'
        kw = f'%{keyword}%'
        rows = db.execute(query, (kw, kw, limit)).fetchall()
        return [Produk(**dict(row)) for row in rows]

    @staticmethod
    def create(nama, deskripsi, harga, stok, gambar, kategori_id, seller_id, tersedia=1, kecamatan='Kendari'):
        db = get_db()
        try:
            cursor = db.execute(
                'INSERT INTO produk (nama, deskripsi, harga, stok, gambar, kategori_id, seller_id, tersedia, kecamatan) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
                (nama, deskripsi, harga, stok, gambar, kategori_id, seller_id, int(tersedia), kecamatan)
            )
            db.commit()
            return cursor.lastrowid
        except Exception as e:
            print(f"Error creating produk: {e}")
            return None

    @staticmethod
    def update(produk_id, nama, deskripsi, harga, stok, gambar, kategori_id, tersedia=1, kecamatan='Kendari'):
        db = get_db()
        db.execute(
            'UPDATE produk SET nama=?, deskripsi=?, harga=?, stok=?, gambar=?, kategori_id=?, tersedia=?, kecamatan=? WHERE id=?',
            (nama, deskripsi, harga, stok, gambar, kategori_id, int(tersedia), kecamatan, produk_id)
        )
        db.commit()

    @staticmethod
    def delete(produk_id):
        db = get_db()
        db.execute('DELETE FROM produk WHERE id = ?', (produk_id,))
        db.commit()

    @staticmethod
    def count():
        db = get_db()
        row = db.execute('SELECT COUNT(*) as cnt FROM produk').fetchone()
        return row['cnt']

    @staticmethod
    def get_all_ids():
        db = get_db()
        rows = db.execute('SELECT id FROM produk').fetchall()
        return [row['id'] for row in rows]

    @staticmethod
    def get_by_ids(ids):
        if not ids:
            return []
        db = get_db()
        placeholders = ','.join(['?' for _ in ids])
        query = Produk._base_query() + f' WHERE p.id IN ({placeholders}) GROUP BY p.id'
        rows = db.execute(query, ids).fetchall()
        return [Produk(**dict(row)) for row in rows]
