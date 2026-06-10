"""
services/ai_chat.py
Chatbot rule-based sederhana untuk platform UMKM Kota Kendari.

Modul ini tidak memakai API eksternal, sehingga aman dari risiko limit
dan lebih mudah dijelaskan dalam skripsi.
"""

import re
from models.database import get_db


STOPWORDS = {
    'ada', 'adakah', 'apakah', 'apa', 'yang', 'dong', 'kak', 'mas', 'mbak',
    'pak', 'bu', 'mau', 'minta', 'ingin', 'pesan', 'beli', 'jual', 'produk',
    'barang', 'stok', 'stock', 'harga', 'berapa', 'dimana', 'di', 'dari',
    'untuk', 'dan', 'atau', 'gak', 'ga', 'nggak', 'nih', 'sih', 'deh', 'ya',
    'oke', 'ok', 'info', 'tanya', 'boleh', 'bisa', 'tolong', 'carikan',
    'rekomendasi', 'rekomendasikan', 'umkm', 'kendari',
}

GREETINGS = {'halo', 'hai', 'hi', 'hello', 'pagi', 'siang', 'sore', 'malam', 'assalamualaikum'}

OUT_OF_TOPIC_KEYWORDS = {
    'politik', 'pemilu', 'agama', 'coding', 'ngoding', 'program', 'python',
    'javascript', 'skripsi', 'matematika', 'berita',
}

CHAT_MEMORY = {}


def _normalize(text: str) -> str:
    return re.sub(r'\s+', ' ', (text or '').strip().lower())


def _tokens(text: str) -> list[str]:
    return re.findall(r'[a-zA-Z0-9]+', _normalize(text))


def _keywords(text: str) -> list[str]:
    words = [word for word in _tokens(text) if word not in STOPWORDS and len(word) > 2]
    return words or [word for word in _tokens(text) if len(word) > 2]


def _format_rupiah(value) -> str:
    return f"Rp {int(value):,}".replace(',', '.')


def _is_available(row) -> bool:
    return int(row['tersedia']) == 1 and int(row['stok']) > 0


def _get_memory(conversation_id: str = None) -> dict:
    if not conversation_id:
        return {}
    return CHAT_MEMORY.setdefault(conversation_id, {})


def _remember_seller(conversation_id: str = None, seller_id: int = None) -> None:
    if conversation_id and seller_id:
        CHAT_MEMORY.setdefault(conversation_id, {})['seller_id'] = seller_id


def _get_seller(seller_id: int):
    if not seller_id:
        return None
    db = get_db()
    return db.execute('''
        SELECT id, nama_lengkap, no_telepon, alamat
        FROM users
        WHERE id = ? AND role = 'seller'
        LIMIT 1
    ''', (seller_id,)).fetchone()


def _find_seller_from_message(message: str):
    db = get_db()
    rows = db.execute('''
        SELECT id, nama_lengkap, no_telepon, alamat
        FROM users
        WHERE role = 'seller'
        ORDER BY LENGTH(nama_lengkap) DESC
    ''').fetchall()

    normalized_message = _normalize(message)
    for row in rows:
        seller_name = _normalize(row['nama_lengkap'])
        if seller_name and seller_name in normalized_message:
            return row

    keywords = _keywords(message)
    for row in rows:
        seller_name = _normalize(row['nama_lengkap'])
        if keywords and all(word in seller_name for word in keywords[:2]):
            return row

    return None


def _resolve_seller_id(message: str, conversation_id: str = None, seller_id: int = None):
    if seller_id:
        _remember_seller(conversation_id, seller_id)
        return seller_id

    mentioned_seller = _find_seller_from_message(message)
    if mentioned_seller:
        _remember_seller(conversation_id, mentioned_seller['id'])
        return mentioned_seller['id']

    memory = _get_memory(conversation_id)
    return memory.get('seller_id')


def _product_query(where_clause: str = '', params: tuple = (), limit: int = 5, seller_id: int = None):
    db = get_db()
    seller_clause = ''
    final_params = list(params)
    if seller_id:
        seller_clause = ' AND p.seller_id = ?' if where_clause else ' WHERE p.seller_id = ?'
        final_params.append(seller_id)

    query = f'''
        SELECT
            p.id,
            p.nama,
            p.deskripsi,
            p.harga,
            p.stok,
            p.tersedia,
            p.kecamatan,
            k.nama AS kategori_nama,
            u.nama_lengkap AS nama_umkm,
            u.no_telepon AS telepon,
            COALESCE(AVG(r.score), 0) AS avg_rating,
            COUNT(r.id) AS total_ulasan
        FROM produk p
        LEFT JOIN kategori k ON p.kategori_id = k.id
        LEFT JOIN users u ON p.seller_id = u.id
        LEFT JOIN ratings r ON p.id = r.produk_id
        {where_clause}
        {seller_clause}
        GROUP BY p.id
        ORDER BY p.tersedia DESC, p.stok DESC, avg_rating DESC, total_ulasan DESC
        LIMIT ?
    '''
    return db.execute(query, (*final_params, limit)).fetchall()


def _search_products(message: str, limit: int = 5, seller_id: int = None):
    words = _keywords(message)
    if not words:
        return []

    db = get_db()
    results = {}
    for word in words:
        pattern = f'%{word}%'
        seller_filter = ' AND p.seller_id = ?' if seller_id else ''
        params = [pattern, pattern, pattern, pattern]
        if seller_id:
            params.append(seller_id)
        rows = db.execute('''
            SELECT
                p.id,
                p.nama,
                p.deskripsi,
                p.harga,
                p.stok,
                p.tersedia,
                p.kecamatan,
                k.nama AS kategori_nama,
                u.nama_lengkap AS nama_umkm,
                u.no_telepon AS telepon,
                COALESCE(AVG(r.score), 0) AS avg_rating,
                COUNT(r.id) AS total_ulasan
            FROM produk p
            LEFT JOIN kategori k ON p.kategori_id = k.id
            LEFT JOIN users u ON p.seller_id = u.id
            LEFT JOIN ratings r ON p.id = r.produk_id
            WHERE (p.nama LIKE ? OR p.deskripsi LIKE ? OR k.nama LIKE ? OR u.nama_lengkap LIKE ?)
            ''' + seller_filter + '''
            GROUP BY p.id
        ''', params).fetchall()

        for row in rows:
            product_id = row['id']
            if product_id not in results:
                results[product_id] = {'row': row, 'score': 0}
            nama = (row['nama'] or '').lower()
            deskripsi = (row['deskripsi'] or '').lower()
            kategori = (row['kategori_nama'] or '').lower()
            seller = (row['nama_umkm'] or '').lower()

            if word in nama:
                results[product_id]['score'] += 5
            if word in kategori:
                results[product_id]['score'] += 3
            if word in seller:
                results[product_id]['score'] += 2
            if word in deskripsi:
                results[product_id]['score'] += 1

    ranked = sorted(
        results.values(),
        key=lambda item: (
            item['score'],
            1 if _is_available(item['row']) else 0,
            float(item['row']['avg_rating']),
            int(item['row']['stok']),
        ),
        reverse=True,
    )
    return [item['row'] for item in ranked[:limit]]


def _format_product_list(rows, intro: str) -> str:
    if not rows:
        return (
            "🙏 Maaf, produk yang kamu cari belum ditemukan di katalog UMKM Kendari. "
            "Coba gunakan kata kunci lain, misalnya nama produk atau kategori."
        )

    lines = [f"🛍️ {intro}"]
    for index, row in enumerate(rows, 1):
        status = "✅ Tersedia" if _is_available(row) else "❌ Habis"
        rating = float(row['avg_rating'])
        rating_text = f" | ⭐ {rating:.1f}" if rating > 0 else ""
        seller = row['nama_umkm'] or 'UMKM Kendari'
        phone = f" | 📞 {row['telepon']}" if row['telepon'] else ""
        lines.append(
            f"{index}. {row['nama']} ({row['kategori_nama'] or 'Umum'})\n"
            f"   💰 {_format_rupiah(row['harga'])} | 📦 Stok {int(row['stok'])} ({status}) | "
            f"{seller}{rating_text}{phone}"
        )
    return "\n".join(lines)


def cek_stok_produk(nama_produk: str, seller_id: int = None) -> str:
    rows = _search_products(nama_produk, limit=5, seller_id=seller_id)
    return _format_product_list(rows, f"Berikut info stok untuk '{nama_produk}':")


def cek_jadwal_toko(seller_id: int = None) -> str:
    try:
        db = get_db()
        seller = _get_seller(seller_id)
        if seller:
            rows = db.execute('''
                SELECT hari_nama, buka_jam, tutup_jam, is_open
                FROM seller_operasional
                WHERE seller_id = ?
                ORDER BY hari_index ASC
            ''', (seller_id,)).fetchall()
            title = f"🕒 Jadwal operasional {seller['nama_lengkap']}:"
        else:
            rows = db.execute('''
                SELECT hari_nama, buka_jam, tutup_jam, is_open
                FROM operasional_toko
                ORDER BY hari_index ASC
            ''').fetchall()
            title = "🕒 Jadwal operasional platform UMKM Kendari:"

        if seller and not rows:
            return f"🕒 Jadwal {seller['nama_lengkap']} belum diatur. Default: Senin-Sabtu 08:00-17:00 WITA, Minggu libur."

        if not rows:
            return "🕒 Jadwal operasional: Senin-Sabtu 08:00-17:00 WITA, Minggu libur."

        lines = [title]
        for row in rows:
            if int(row['is_open']) == 1:
                lines.append(f"- {row['hari_nama']}: {row['buka_jam']} - {row['tutup_jam']} WITA")
            else:
                lines.append(f"- {row['hari_nama']}: Libur")
        return "\n".join(lines)
    except Exception:
        return "🕒 Jadwal operasional: Senin-Sabtu 08:00-17:00 WITA, Minggu libur."


def cari_produk(nama_produk: str, seller_id: int = None) -> str:
    rows = _search_products(nama_produk, limit=5, seller_id=seller_id)
    return _format_product_list(rows, f"Berikut produk yang cocok dengan '{nama_produk}':")


def _list_categories() -> str:
    db = get_db()
    rows = db.execute('''
        SELECT k.nama, COUNT(p.id) AS jumlah
        FROM kategori k
        LEFT JOIN produk p ON p.kategori_id = k.id
        GROUP BY k.id
        ORDER BY k.nama ASC
    ''').fetchall()
    if not rows:
        return "🙏 Belum ada data kategori produk."

    lines = ["🏷️ Kategori produk yang tersedia:"]
    for row in rows:
        lines.append(f"- {row['nama']} ({int(row['jumlah'])} produk)")
    return "\n".join(lines)


def _popular_products(seller_id: int = None) -> str:
    rows = _product_query(limit=5, seller_id=seller_id)
    return _format_product_list(rows, "Rekomendasi produk UMKM Kendari:")


def _seller_context_text(seller_id: int = None) -> str:
    seller = _get_seller(seller_id)
    if not seller:
        return ''
    return f"📌 Konteks toko saat ini: {seller['nama_lengkap']}."


def _extract_context_products(extra_context: str) -> str:
    if not extra_context:
        return ''

    lower_context = extra_context.lower()
    if 'produk' not in lower_context and 'stok' not in lower_context:
        return ''

    return (
        "📌 Berdasarkan konteks UMKM yang diberikan, saya cocokkan pertanyaan pelanggan "
        "dengan daftar produk toko tersebut."
    )


def get_ai_response(
    user_message: str,
    extra_context: str = '',
    system_prompt: str = '',
    conversation_id: str = None,
    seller_id: int = None,
) -> str:
    """
    Menghasilkan jawaban chatbot dengan aturan sederhana.

    conversation_id dipakai untuk memory sederhana agar konteks toko tidak mudah hilang.
    Parameter system_prompt dipertahankan agar kompatibel dengan endpoint n8n lama.
    """
    message = _normalize(user_message)
    active_seller_id = _resolve_seller_id(message, conversation_id=conversation_id, seller_id=seller_id)
    context = _extract_context_products(extra_context or system_prompt)
    seller_context = _seller_context_text(active_seller_id)

    if not message:
        return "😊 Silakan ketik pertanyaan tentang produk UMKM Kendari."

    words = set(_tokens(message))

    if words & OUT_OF_TOPIC_KEYWORDS:
        return (
            "🙏 Maaf, saya hanya membantu pertanyaan seputar produk, harga, stok, "
            "kategori, dan jadwal operasional UMKM Kendari."
        )

    if words & GREETINGS and len(words) <= 3:
        return (
            "😊 Halo! Saya asisten UMKM Kendari. Kamu bisa tanya produk, harga, stok, "
            "kategori, atau jadwal operasional toko."
        )

    if seller_context and not any(word in message for word in ['jadwal', 'jam buka', 'buka jam', 'tutup', 'operasional', 'hari buka', 'stok', 'stock', 'tersedia', 'ada barang', 'masih ada', 'harga', 'berapa', 'cari', 'produk', 'beli', 'jual', 'pesan']):
        rows = _search_products(message, limit=5, seller_id=active_seller_id)
        if not rows:
            return f"{seller_context}\nAda yang ingin kamu tanyakan tentang produk, stok, harga, atau jadwal toko ini? 😊"

    if any(word in message for word in ['jadwal', 'jam buka', 'buka jam', 'tutup', 'operasional', 'hari buka']):
        prefix = f"{seller_context}\n" if seller_context else ''
        return prefix + cek_jadwal_toko(active_seller_id)

    if any(word in message for word in ['kategori', 'jenis produk', 'macam produk']):
        return _list_categories()

    if any(word in message for word in ['rekomendasi', 'rekomendasikan', 'produk populer', 'terlaris']):
        prefix = f"{seller_context}\n" if seller_context else ''
        return prefix + _popular_products(active_seller_id)

    if any(word in message for word in ['stok', 'stock', 'tersedia', 'ada barang', 'masih ada']):
        prefix = f"{seller_context}\n" if seller_context else ''
        return prefix + cek_stok_produk(message, active_seller_id)

    if any(word in message for word in ['harga', 'berapa', 'cari', 'produk', 'beli', 'jual', 'pesan']):
        prefix = f"{seller_context}\n" if seller_context else ''
        return prefix + cari_produk(message, active_seller_id)

    rows = _search_products(message, limit=5, seller_id=active_seller_id)
    if rows:
        intro = "Saya menemukan beberapa produk yang mungkin sesuai:"
        if context:
            intro = f"{context}\n\n{intro}"
        if seller_context:
            intro = f"{seller_context}\n{intro}"
        return _format_product_list(rows, intro)

    return (
        "🙏 Maaf, saya belum menemukan jawaban yang cocok. Coba tanyakan dengan kata kunci "
        "produk, kategori, harga, stok, atau jadwal operasional UMKM Kendari."
    )

