from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify, session
from flask_login import login_required, current_user
from models.produk import Produk
from models.kategori import Kategori
from models.rating import Rating
from recommendation.engine import get_recommendations
from datetime import datetime
import re

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
def index():
    """Halaman utama dengan rekomendasi produk."""
    page = request.args.get('page', 1, type=int)
    per_page = 12

    # Produk yang direkomendasikan dan trending tetap ditampilkan di halaman 1
    produk_trending = []
    produk_rekomendasi = []
    rekomendasi = {'method': '', 'reason': '', 'products': []}
    
    if page == 1:
        produk_trending = Produk.get_trending(limit=4)
        user_id = current_user.id if current_user.is_authenticated else None
        rekomendasi = get_recommendations(user_id, n=4)
        produk_rekomendasi = Produk.get_by_ids(rekomendasi['products']) if rekomendasi['products'] else []

    # Semua produk dengan pagination
    all_produk = Produk.get_all()
    # Filter hanya yang tersedia
    all_produk = [p for p in all_produk if p.tersedia]

    total = len(all_produk)
    total_pages = max(1, (total + per_page - 1) // per_page)
    page = min(page, total_pages) if total > 0 else 1
    start = (page - 1) * per_page
    
    produk_paginasi = all_produk[start:start + per_page]
    kategori_list = Kategori.get_all()

    return render_template('index.html',
                           produk_paginasi=produk_paginasi,
                           produk_trending=produk_trending,
                           produk_rekomendasi=produk_rekomendasi,
                           rekomendasi_method=rekomendasi['method'],
                           rekomendasi_reason=rekomendasi['reason'],
                           kategori_list=kategori_list,
                           page=page,
                           total_pages=total_pages,
                           total=total)


@main_bp.route('/produk/<int:produk_id>')
def detail_produk(produk_id):
    """Halaman detail produk dan rating."""
    produk = Produk.get_by_id(produk_id)
    if not produk:
        flash('Produk tidak ditemukan', 'warning')
        return redirect(url_for('main.index'))

    reviews = Rating.get_by_produk(produk_id)

    user_rating = None
    if current_user.is_authenticated:
        user_rating = Rating.get_by_user_and_produk(current_user.id, produk_id)

    from recommendation.knn import get_knn_data_from_db, knn_recommend_similar
    products_data, kategori_ids = get_knn_data_from_db()
    similar_ids = knn_recommend_similar(produk_id, products_data, kategori_ids, n_recommendations=4)
    produk_serupa = Produk.get_by_ids(similar_ids)

    kategori_list = Kategori.get_all()

    return render_template('produk/detail.html',
                           produk=produk,
                           reviews=reviews,
                           user_rating=user_rating,
                           produk_serupa=produk_serupa,
                           kategori_list=kategori_list)


@main_bp.route('/produk/<int:produk_id>/rating', methods=['POST'])
@login_required
def submit_rating(produk_id):
    """Submit atau update rating produk."""
    score = request.form.get('score', type=int)
    review = request.form.get('review', '').strip()

    if not score or score < 1 or score > 5:
        flash('Rating harus antara 1-5', 'danger')
        return redirect(url_for('main.detail_produk', produk_id=produk_id))

    Rating.create_or_update(current_user.id, produk_id, score, review)

    # Trigger NCF retrain jika user baru melewati threshold
    from recommendation.engine import on_new_rating
    on_new_rating(current_user.id)

    flash('Rating berhasil disimpan!', 'success')
    return redirect(url_for('main.detail_produk', produk_id=produk_id))





@main_bp.route('/produk')
def list_produk():
    """Daftar semua produk dengan filter kecamatan."""

    kecamatan = request.args.get('kecamatan', '')
    kategori_id = request.args.get('kategori', type=int)
    page = request.args.get('page', 1, type=int)
    per_page = 12

    if kecamatan:
        all_produk = Produk.get_by_kecamatan(kecamatan)
    elif kategori_id:
        all_produk = Produk.get_by_kategori(kategori_id)
    else:
        all_produk = Produk.get_all()

    # Simple pagination
    total = len(all_produk)
    total_pages = max(1, (total + per_page - 1) // per_page)
    page = min(page, total_pages)
    start = (page - 1) * per_page
    produk_list = all_produk[start:start + per_page]

    kategori_list = Kategori.get_all()
    kecamatan_list = Produk.get_kecamatan_list()

    return render_template('produk/list.html',
                           produk_list=produk_list,
                           kategori_list=kategori_list,
                           kecamatan_list=kecamatan_list,
                           selected_kecamatan=kecamatan,
                           page=page,
                           total_pages=total_pages,
                           total=total)


@main_bp.route('/search')
def search():
    """Pencarian produk dengan pagination."""
    keyword = request.args.get('q', '').strip()
    if not keyword:
        return redirect(url_for('main.index'))

    page = request.args.get('page', 1, type=int)
    per_page = 12
    all_results = Produk.search(keyword, limit=100)

    total = len(all_results)
    total_pages = max(1, (total + per_page - 1) // per_page)
    page = min(page, total_pages)
    start = (page - 1) * per_page
    results = all_results[start:start + per_page]

    kategori_list = Kategori.get_all()

    return render_template('produk/list.html',
                           produk_list=results,
                           search_keyword=keyword,
                           kategori_list=kategori_list,
                           page=page,
                           total_pages=total_pages,
                           total=total)


@main_bp.route('/tentang')
def tentang():
    """Halaman tentang sistem — penjelasan algoritma KNN & NCF."""
    kategori_list = Kategori.get_all()
    return render_template('tentang.html', kategori_list=kategori_list)


@main_bp.route('/profil')
@login_required
def profil():
    """Halaman profil user."""
    user_ratings = Rating.get_by_user(current_user.id)
    rating_count = len(user_ratings)
    kategori_list = Kategori.get_all()

    return render_template('user/profil.html',
                           user_ratings=user_ratings,
                           rating_count=rating_count,
                           kategori_list=kategori_list)


# ============ CHATBOT API ============

@main_bp.route('/chatbot')
def chatbot_page():
    """Halaman chatbot."""
    kategori_list = Kategori.get_all()
    return render_template('chatbot.html', kategori_list=kategori_list)


@main_bp.route('/api/chat', methods=['POST'])
def chat_api():
    """API chatbot rekomendasi."""
    data = request.get_json()
    message = data.get('message', '').strip().lower() if data else ''

    if not message:
        return jsonify({'reply': 'Silakan ketik pesan Anda 😊', 'products': []})

    user_id = current_user.id if current_user.is_authenticated else None
    from models.database import get_db
    db = get_db()

    day_names = ['senin', 'selasa', 'rabu', 'kamis', 'jumat', 'sabtu', 'minggu']
    day_names_title = ['Senin', 'Selasa', 'Rabu', 'Kamis', 'Jumat', 'Sabtu', 'Minggu']

    def get_store_schedule():
        try:
            rows = db.execute('''
                SELECT hari_index, hari_nama, buka_jam, tutup_jam, is_open
                FROM operasional_toko
                ORDER BY hari_index ASC
            ''').fetchall()
            return [dict(r) for r in rows]
        except Exception:
            return []

    def get_today_store_status():
        today_idx = datetime.now().weekday()  # Senin=0 ... Minggu=6
        try:
            row = db.execute('''
                SELECT hari_nama, buka_jam, tutup_jam, is_open
                FROM operasional_toko
                WHERE hari_index = ?
            ''', (today_idx,)).fetchone()
            if row:
                return dict(row), today_idx
        except Exception:
            pass
        # Fallback jika tabel belum terisi lengkap
        fallback_open = 0 if today_idx == 6 else 1
        return {
            'hari_nama': day_names_title[today_idx],
            'buka_jam': '08:00',
            'tutup_jam': '17:00',
            'is_open': fallback_open
        }, today_idx

    def get_today_seller_status(seller_id):
        today_idx = datetime.now().weekday()
        try:
            row = db.execute(
                '''
                SELECT hari_nama, buka_jam, tutup_jam, is_open
                FROM seller_operasional
                WHERE seller_id = ? AND hari_index = ?
                ''',
                (seller_id, today_idx)
            ).fetchone()
            if row:
                return dict(row), today_idx
        except Exception:
            pass
        # fallback ke jadwal umum
        return get_today_store_status()

    def extract_store_query(msg):
        cleaned = msg.lower()
        for token in [
            'apakah', 'tolong', 'cek', 'status', 'hari ini', 'jam', 'operasional',
            'buka', 'tutup', 'kah', '?'
        ]:
            cleaned = cleaned.replace(token, ' ')
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        return re.sub(r'\s+', ' ', cleaned).strip()

    def format_store_hours():
        rows = get_store_schedule()
        if not rows:
            return '• Senin - Sabtu: 08:00 - 17:00 WITA\n• Minggu: Libur'

        lines = []
        for row in rows:
            if int(row.get('is_open') or 0) == 1:
                lines.append(f"• {row['hari_nama']}: {row['buka_jam']} - {row['tutup_jam']} WITA")
            else:
                lines.append(f"• {row['hari_nama']}: Libur")
        return '\n'.join(lines)

    def produk_to_card(p):
        """Konversi Produk ke dict untuk render kartu."""
        url = p.gambar if p.gambar else 'default.jpg'
        stok_value = int(p.stok or 0)
        is_ready = bool(p.tersedia) and stok_value > 0
        return {
            'id': p.id,
            'nama': p.nama,
            'harga': p.harga,
            'harga_fmt': f"Rp {p.harga:,.0f}",
            'kategori': p.kategori_nama or 'Umum',
            'avg_rating': round(p.avg_rating, 1),
            'total_rating': p.total_rating,
            'stars': '★' * round(p.avg_rating) + '☆' * (5 - round(p.avg_rating)),
            'stok': stok_value,
            'stok_text': f"Stok {stok_value}",
            'ready_stock': is_ready,
            'gambar_url': url_for('static', filename='uploads/' + url),
            'detail_url': url_for('main.detail_produk', produk_id=p.id),
        }

    def rows_to_cards(rows):
        """Konversi DB rows ke cards."""
        cards = []
        for r in rows:
            r = dict(r)
            url = r.get('gambar', 'default.jpg') or 'default.jpg'
            stok_value = int(r.get('stok') or 0)
            is_ready = bool(r.get('tersedia')) and stok_value > 0
            cards.append({
                'id': r['id'],
                'nama': r['nama'],
                'harga_fmt': f"Rp {r['harga']:,.0f}",
                'kategori': r.get('kategori_nama') or 'Umum',
                'avg_rating': round(r.get('avg_rating') or 0, 1),
                'total_rating': r.get('total_rating') or 0,
                'stars': '★' * round(r.get('avg_rating') or 0) + '☆' * (5 - round(r.get('avg_rating') or 0)),
                'stok': stok_value,
                'stok_text': f"Stok {stok_value}",
                'ready_stock': is_ready,
                'gambar_url': url_for('static', filename='uploads/' + url),
                'detail_url': url_for('main.detail_produk', produk_id=r['id']),
            })
        return cards

    # Intent: Salam
    if any(w in message for w in ['halo', 'hai', 'hi', 'selamat', 'pagi', 'siang', 'sore', 'malam', 'hey']):
        return jsonify({
            'reply': 'Halo! 👋 Saya asisten UMKM Kendari.\n\nSaya bisa membantu Anda mengecek:\n• **Jadwal buka toko** (contoh: "toko hari ini buka?")\n• **Ketersediaan stok** (contoh: "stok sinonggi ada?")', 
            'products': []
        })

    # Intent: Status toko spesifik (contoh: "toko kuliner hari ini buka?")
    if any(w in message for w in ['buka', 'tutup', 'operasional', 'jam']) and 'toko' in message:
        store_query = extract_store_query(message)
        if store_query:
            query_norm = store_query.strip().lower()
            query_no_toko = query_norm.replace('toko ', '').replace('toko_', '').strip()
            search_terms = [query_norm]
            if query_no_toko and query_no_toko not in search_terms:
                search_terms.append(query_no_toko)
            if query_no_toko:
                search_terms.append(f"toko {query_no_toko}")
                search_terms.append(f"toko_{query_no_toko}")

            sellers = db.execute(
                '''
                SELECT id, username, nama_lengkap
                FROM users
                WHERE role = 'seller'
                  AND (
                    LOWER(username) LIKE ?
                    OR LOWER(nama_lengkap) LIKE ?
                    OR LOWER(REPLACE(username, '_', ' ')) LIKE ?
                    OR LOWER(username) LIKE ?
                    OR LOWER(nama_lengkap) LIKE ?
                  )
                ORDER BY nama_lengkap ASC
                LIMIT 5
                ''',
                (
                    f'%{search_terms[0]}%',
                    f'%{search_terms[0]}%',
                    f'%{search_terms[0]}%',
                    f'%{search_terms[1] if len(search_terms) > 1 else search_terms[0]}%',
                    f'%{search_terms[2] if len(search_terms) > 2 else search_terms[0]}%',
                )
            ).fetchall()

            if len(sellers) == 1:
                seller = dict(sellers[0])
                today_status, _ = get_today_seller_status(seller['id'])
                is_open = int(today_status.get('is_open') or 0) == 1
                status_text = '✅ Buka' if is_open else '❌ Tutup'
                jam_text = (
                    f" ({today_status.get('buka_jam')} - {today_status.get('tutup_jam')} WITA)"
                    if is_open else ''
                )
                return jsonify({
                    'reply': (
                        f"🕒 **Status {seller.get('nama_lengkap')} hari ini ({today_status.get('hari_nama')}):** "
                        f"{status_text}{jam_text}"
                    ),
                    'products': []
                })

            if len(sellers) > 1:
                names = '\n'.join([f"• {s['nama_lengkap']}" for s in sellers])
                return jsonify({
                    'reply': (
                        f'Saya menemukan beberapa toko untuk kata kunci **"{store_query}"**:\n{names}\n\n'
                        'Sebutkan nama toko yang lebih spesifik ya.'
                    ),
                    'products': []
                })

            # Fallback: cari toko lewat produk terkait (jika user menyebut jenis produk)
            fallback_seller = db.execute(
                '''
                SELECT DISTINCT u.id, u.username, u.nama_lengkap
                FROM users u
                JOIN produk p ON p.seller_id = u.id
                WHERE u.role = 'seller'
                  AND (LOWER(p.nama) LIKE ? OR LOWER(p.deskripsi) LIKE ?)
                ORDER BY u.nama_lengkap ASC
                LIMIT 1
                ''',
                (f'%{query_no_toko or query_norm}%', f'%{query_no_toko or query_norm}%')
            ).fetchone()
            if fallback_seller:
                seller = dict(fallback_seller)
                today_status, _ = get_today_seller_status(seller['id'])
                is_open = int(today_status.get('is_open') or 0) == 1
                status_text = '✅ Buka' if is_open else '❌ Tutup'
                jam_text = (
                    f" ({today_status.get('buka_jam')} - {today_status.get('tutup_jam')} WITA)"
                    if is_open else ''
                )
                return jsonify({
                    'reply': (
                        f"🕒 Saya asumsikan maksud Anda toko **{seller.get('nama_lengkap')}**.\n"
                        f"Status hari ini ({today_status.get('hari_nama')}): {status_text}{jam_text}"
                    ),
                    'products': []
                })

            return jsonify({
                'reply': f'Saya belum menemukan toko dengan nama **"{store_query}"**.',
                'products': []
            })

    # Intent: Status toko hari ini / jam operasional
    if any(w in message for w in ['buka hari ini', 'hari ini buka', 'toko buka', 'jam buka', 'jam operasional', 'operasional', 'tutup hari ini']):
        session.pop('chat_context', None)
        today_status, _ = get_today_store_status()
        status_text = '✅ Buka' if int(today_status.get('is_open') or 0) == 1 else '❌ Tutup'
        if int(today_status.get('is_open') or 0) == 1:
            now_reply = f"{status_text} ({today_status.get('buka_jam')} - {today_status.get('tutup_jam')} WITA)"
        else:
            now_reply = status_text

        return jsonify({
            'reply': (
                f"🕒 **Status toko hari ini ({today_status.get('hari_nama')}):** {now_reply}\n\n"
                f"**Jadwal operasional:**\n{format_store_hours()}"
            ),
            'products': []
        })

    # Intent: Cek stok spesifik
    if any(w in message for w in ['stok', 'stock', 'ready', 'tersedia', 'kosong']):
        raw_query = message
        for w in [
            'cek', 'tolong', 'dong', 'apakah', 'ada', 'ga', 'nggak', 'tidak',
            'stok', 'stock', 'ready', 'tersedia', 'kosong', 'produk', '?'
        ]:
            raw_query = raw_query.replace(w, ' ')
        raw_query = re.sub(r'\s+', ' ', raw_query).strip()

        if not raw_query:
            return jsonify({
                'reply': 'Sebutkan nama produknya ya. Contoh: **"stok sinonggi ada?"**.',
                'products': []
            })

        rows = db.execute('''
            SELECT p.*, k.nama as kategori_nama,
                   COALESCE(AVG(r.score), 0) as avg_rating, COUNT(r.id) as total_rating
            FROM produk p
            LEFT JOIN kategori k ON p.kategori_id = k.id
            LEFT JOIN ratings r ON p.id = r.produk_id
            WHERE p.nama LIKE ? OR p.deskripsi LIKE ?
            GROUP BY p.id
            ORDER BY p.stok DESC, p.created_at DESC
            LIMIT 5
        ''', (f'%{raw_query}%', f'%{raw_query}%')).fetchall()

        if not rows:
            return jsonify({
                'reply': f'Saya belum menemukan produk **"{raw_query}"** di katalog.',
                'products': []
            })

        available_rows = [r for r in rows if int(dict(r).get('stok') or 0) > 0 and int(dict(r).get('tersedia') or 0) == 1]
        cards = rows_to_cards(available_rows if available_rows else rows)

        first = dict(rows[0])
        stok_first = int(first.get('stok') or 0)
        is_ready_first = int(first.get('tersedia') or 0) == 1 and stok_first > 0

        if is_ready_first:
            reply = f'✅ Produk **{first.get("nama")}** tersedia dengan **stok {stok_first}**.'
        else:
            reply = f'❌ Produk **{first.get("nama")}** sedang kosong/habis.'

        if len(rows) > 1:
            reply += '\n\nBerikut produk terkait yang saya temukan:'
        return jsonify({'reply': reply, 'products': cards})

    # Intent: Terima kasih
    if any(w in message for w in ['terima kasih', 'makasih', 'thanks', 'thx', 'ok', 'oke', 'sip']):
        return jsonify({'reply': 'Sama-sama! 😊 Ada yang lain yang ingin ditanyakan terkait jadwal buka atau stok?', 'products': []})

    # Default
    return jsonify({
        'reply': 'Hmm, saya kurang paham 🤔\n\nSaya hanya bisa membantu mengecek:\n• **Jadwal buka toko** (contoh: "toko hari ini buka?")\n• **Ketersediaan stok** (contoh: "stok sinonggi ada?")', 
        'products': []
    })

