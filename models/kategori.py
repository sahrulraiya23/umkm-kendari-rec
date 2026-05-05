from models.database import get_db


class Kategori:
    """Model Kategori produk UMKM."""

    def __init__(self, id, nama, deskripsi='', icon='bi-tag'):
        self.id = id
        self.nama = nama
        self.deskripsi = deskripsi
        self.icon = icon

    @staticmethod
    def get_all():
        db = get_db()
        rows = db.execute('SELECT * FROM kategori ORDER BY nama').fetchall()
        return [Kategori(**dict(row)) for row in rows]

    @staticmethod
    def get_by_id(kategori_id):
        db = get_db()
        row = db.execute('SELECT * FROM kategori WHERE id = ?', (kategori_id,)).fetchone()
        if row:
            return Kategori(**dict(row))
        return None

    @staticmethod
    def create(nama, deskripsi='', icon='bi-tag'):
        db = get_db()
        try:
            db.execute('INSERT INTO kategori (nama, deskripsi, icon) VALUES (?, ?, ?)',
                       (nama, deskripsi, icon))
            db.commit()
            return True
        except Exception as e:
            print(f"Error creating kategori: {e}")
            return False

    @staticmethod
    def update(kategori_id, nama, deskripsi='', icon='bi-tag'):
        db = get_db()
        db.execute('UPDATE kategori SET nama=?, deskripsi=?, icon=? WHERE id=?',
                   (nama, deskripsi, icon, kategori_id))
        db.commit()

    @staticmethod
    def delete(kategori_id):
        db = get_db()
        db.execute('DELETE FROM kategori WHERE id = ?', (kategori_id,))
        db.commit()

    @staticmethod
    def count():
        db = get_db()
        row = db.execute('SELECT COUNT(*) as cnt FROM kategori').fetchone()
        return row['cnt']
