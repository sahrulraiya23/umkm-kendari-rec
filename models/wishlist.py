from models.database import get_db


class Wishlist:
    """Model Wishlist/Favorit produk."""

    def __init__(self, id, user_id, produk_id, created_at=None, **kwargs):
        self.id = id
        self.user_id = user_id
        self.produk_id = produk_id
        self.created_at = created_at
        self.produk_nama = kwargs.get('produk_nama', '')
        self.produk_harga = kwargs.get('produk_harga', 0)
        self.produk_gambar = kwargs.get('produk_gambar', 'default.jpg')
        self.kategori_nama = kwargs.get('kategori_nama', '')

    @staticmethod
    def is_wishlisted(user_id, produk_id):
        db = get_db()
        row = db.execute('SELECT id FROM wishlist WHERE user_id = ? AND produk_id = ?',
                         (user_id, produk_id)).fetchone()
        return row is not None

    @staticmethod
    def toggle(user_id, produk_id):
        """Toggle wishlist: tambah jika belum ada, hapus jika sudah ada. Return True jika ditambah."""
        db = get_db()
        existing = db.execute('SELECT id FROM wishlist WHERE user_id = ? AND produk_id = ?',
                              (user_id, produk_id)).fetchone()
        if existing:
            db.execute('DELETE FROM wishlist WHERE id = ?', (existing['id'],))
            db.commit()
            return False
        else:
            db.execute('INSERT INTO wishlist (user_id, produk_id) VALUES (?, ?)',
                       (user_id, produk_id))
            db.commit()
            return True

    @staticmethod
    def get_by_user(user_id):
        db = get_db()
        rows = db.execute('''
            SELECT w.*, p.nama as produk_nama, p.harga as produk_harga,
                   p.gambar as produk_gambar, k.nama as kategori_nama
            FROM wishlist w
            JOIN produk p ON w.produk_id = p.id
            LEFT JOIN kategori k ON p.kategori_id = k.id
            WHERE w.user_id = ?
            ORDER BY w.created_at DESC
        ''', (user_id,)).fetchall()
        return [Wishlist(**dict(row)) for row in rows]

    @staticmethod
    def count_by_user(user_id):
        db = get_db()
        row = db.execute('SELECT COUNT(*) as cnt FROM wishlist WHERE user_id = ?', (user_id,)).fetchone()
        return row['cnt']
