from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify, session
from flask_login import login_required, current_user
from models.produk import Produk
from models.kategori import Kategori
from models.rating import Rating
from recommendation.engine import get_recommendations
from datetime import datetime
from config import AI_ENABLED
import re
import uuid

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
    """Redirect ke halaman utama karena chatbot sekarang berupa widget."""
    return redirect(url_for('main.index'))


@main_bp.route('/api/chat', methods=['POST'])
def chat_api():
    """API chatbot rekomendasi rule-based."""
    data = request.get_json()
    message = data.get('message', '').strip().lower() if data else ''

    if not message:
        return jsonify({'reply': 'Silakan ketik pesan Anda 😊', 'products': []})

    if not AI_ENABLED:
        return jsonify({
            'reply': 'Maaf, fitur chatbot saat ini sedang dinonaktifkan.',
            'products': []
        })

    try:
        from services.ai_chat import get_ai_response
        if 'chatbot_conversation_id' not in session:
            session['chatbot_conversation_id'] = str(uuid.uuid4())
        ai_reply = get_ai_response(
            message,
            conversation_id=session['chatbot_conversation_id']
        )
        return jsonify({'reply': ai_reply, 'products': []})

    except Exception as e:
        print(f'[Chatbot Error] {e}')
        return jsonify({
            'reply': 'Maaf, chatbot sedang mengalami gangguan. Silakan coba lagi nanti.',
            'products': []
        })

