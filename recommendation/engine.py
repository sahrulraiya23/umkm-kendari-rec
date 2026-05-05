"""
Switching Hybrid Recommendation Engine.
KNN digunakan saat cold-start (user baru / rating < NCF_MIN_RATINGS).
NCF digunakan setelah user memiliki cukup histori rating (>= NCF_MIN_RATINGS) dan model sudah di-training.
Kedua algoritma berjalan EKSKLUSIF -- tidak pernah digabungkan/blended.

Logika switching:
- User belum login               -> KNN generik (produk populer)
- Login + preferensi + <3 rating -> KNN personalized (kategori + budget + rating_min)
- Login + >=3 rating + model ada + user dikenal model -> NCF
- Login + >=3 rating + model BELUM ada / user TIDAK dikenal -> trigger bg-retrain, pakai KNN sementara
- Fallback                       -> KNN generik

Transisi KNN → NCF:
- Ketika user submit rating ke-N (N = NCF_MIN_RATINGS), sistem otomatis trigger
  background retrain sehingga di refresh berikutnya NCF sudah bisa digunakan.
- Selama model belum siap, user tetap dilayani KNN.
- Background retrain menggunakan epochs rendah (15) untuk kecepatan.
- Admin bisa retrain penuh (50 epochs) via /admin/train-model.
"""

import threading
from config import NCF_MIN_RATINGS
from recommendation.knn import knn_recommend, knn_recommend_personalized, get_knn_data_from_db
from recommendation.ncf import ncf_recommend


def get_recommendations(user_id=None, n=8):
    """
    Mendapatkan rekomendasi produk untuk user.

    Args:
        user_id: ID user (None jika belum login)
        n: jumlah rekomendasi

    Returns:
        dict: {
            'products': list of produk_ids,
            'method': 'knn' atau 'ncf',
            'reason': penjelasan
        }
    """
    from models.rating import Rating
    from models.produk import Produk
    from models.preference import UserPreference

    # Jika user belum login, gunakan KNN generik
    if user_id is None:
        return _knn_fallback(n, reason="User belum login, menggunakan KNN cold-start")

    # Hitung jumlah rating user
    rating_count = Rating.count_by_user(user_id)

    # === Fase NCF: user punya cukup rating ===
    if rating_count >= NCF_MIN_RATINGS:
        # Coba gunakan NCF
        all_produk_ids = Produk.get_all_ids()
        rated_produk_ids = Rating.get_user_rated_produk_ids(user_id)

        ncf_result = ncf_recommend(user_id, all_produk_ids, rated_produk_ids, n)

        if ncf_result:
            return {
                'products': ncf_result,
                'method': 'ncf',
                'reason': f'Neural Collaborative Filtering ({rating_count} rating tersedia)'
            }

        # NCF gagal: model belum ada atau user tidak dikenal model → trigger bg-retrain
        _trigger_bg_retrain()

        # Sementara NCF belum siap, gunakan KNN  
        # Cek apakah user punya preferensi — jika ya, pakai personalized
        has_prefs = UserPreference.has_preferences(user_id)
        if has_prefs:
            return _knn_personalized(
                user_id, n, UserPreference,
                extra_note=" | NCF: model sedang diperbarui"
            )

        return _knn_fallback(
            n, reason=f"KNN sementara — NCF sedang diperbarui ({rating_count} rating)"
        )

    # === Fase KNN: user masih cold-start ===
    # Cek apakah user punya preferensi dari onboarding
    has_prefs = UserPreference.has_preferences(user_id)

    if has_prefs:
        # KNN personalized berdasarkan preferensi user
        return _knn_personalized(user_id, n, UserPreference)

    # Fallback ke KNN generik
    return _knn_fallback(
        n, reason=f"KNN Cold-Start ({rating_count} rating, butuh ≥{NCF_MIN_RATINGS} untuk NCF)"
    )


def _knn_personalized(user_id, n, UserPreference, extra_note=""):
    """KNN Personalized recommendation berdasarkan preferensi user."""
    preferred_kat_ids = UserPreference.get_preferred_kategori_ids(user_id)
    harga_min, harga_max = UserPreference.get_price_range(user_id)
    rating_min = UserPreference.get_rating_min(user_id)
    sort_by = UserPreference.get_sort_by(user_id)

    products_data, kategori_ids = get_knn_data_from_db()
    knn_result = knn_recommend_personalized(
        products_data, kategori_ids,
        preferred_kat_ids, harga_min, harga_max,
        rating_min=rating_min, sort_by=sort_by, n_recommendations=n
    )

    pref_info = []
    if preferred_kat_ids:
        pref_info.append(f"{len(preferred_kat_ids)} kategori favorit")
    if harga_max < 999999999:
        pref_info.append(f"budget Rp{harga_min:,.0f}-Rp{harga_max:,.0f}")
    if rating_min > 1:
        pref_info.append(f"rating ≥{rating_min:.1f}")

    return {
        'products': knn_result,
        'method': 'knn',
        'reason': f'KNN Personalized ({", ".join(pref_info) if pref_info else "berdasarkan preferensi"}){extra_note}'
    }


def _knn_fallback(n, reason):
    """Fallback recommendation menggunakan KNN generik."""
    products_data, kategori_ids = get_knn_data_from_db()
    knn_result = knn_recommend(products_data, kategori_ids, n)

    return {
        'products': knn_result,
        'method': 'knn',
        'reason': reason
    }


def on_new_rating(user_id):
    """
    Dipanggil setelah user memberi rating baru.
    Cek apakah user baru saja melewati threshold NCF_MIN_RATINGS,
    dan jika ya, trigger background retrain supaya NCF siap di refresh berikutnya.
    
    Args:
        user_id: ID user yang baru memberi rating
    """
    from models.rating import Rating
    rating_count = Rating.count_by_user(user_id)

    if rating_count >= NCF_MIN_RATINGS:
        # User sudah melewati threshold → pastikan model NCF diperbarui
        _trigger_bg_retrain()


# ── Background Re-training ────────────────────────────────────────────────────
import time

_retrain_lock = threading.Lock()
_retrain_in_progress = False
_last_retrain_attempt = 0
_RETRAIN_COOLDOWN = 300  # 5 menit cooldown antar percobaan retrain


def _trigger_bg_retrain():
    """
    Jalankan training NCF di background thread agar request user tidak terhambat.
    Hanya satu training boleh berjalan pada satu waktu.
    Cooldown 5 menit antar percobaan retrain untuk menghindari overhead.
    Perlu capture Flask app untuk membuat app_context() di thread baru.
    """
    global _retrain_in_progress, _last_retrain_attempt
    from flask import current_app

    # Cooldown: jangan trigger terlalu sering
    now = time.time()
    if now - _last_retrain_attempt < _RETRAIN_COOLDOWN:
        return
    _last_retrain_attempt = now

    # Cek flag di luar lock untuk fast-path (menghindari blocking)
    if _retrain_in_progress:
        return  # Sudah ada training yang sedang berjalan

    # Capture Flask app object SEBELUM masuk thread (harus dalam request context)
    try:
        app = current_app._get_current_object()
    except RuntimeError:
        print('[BG-Retrain] Tidak bisa mendapatkan app context, skip.')
        return

    def _do_train():
        global _retrain_in_progress
        # Acquire lock SEBELUM set flag — mencegah race condition
        if not _retrain_lock.acquire(blocking=False):
            return  # Ada thread lain yang sudah menjalankan training
        try:
            _retrain_in_progress = True
            with app.app_context():
                from models.rating import Rating as _Rating
                from recommendation.ncf import train_ncf_model
                from config import NCF_MIN_RATINGS
                ratings_data = _Rating.get_all_for_training()
                
                # Gunakan NCF_MIN_RATINGS sebagai syarat agar user pertama bisa train
                if len(ratings_data) >= NCF_MIN_RATINGS:
                    # epochs rendah agar cepat selesai
                    train_ncf_model(ratings_data, epochs=15)
                    print(f'[BG-Retrain] Selesai. {len(ratings_data)} rating diproses.')
                else:
                    print(f'[BG-Retrain] Skip — hanya {len(ratings_data)} rating (minimal {NCF_MIN_RATINGS}).')
        except Exception as e:
            print(f'[BG-Retrain] Error: {e}')
        finally:
            _retrain_in_progress = False
            _retrain_lock.release()

    t = threading.Thread(target=_do_train, daemon=True)
    t.start()
