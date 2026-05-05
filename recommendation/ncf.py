"""
Neural Collaborative Filtering (NCF) untuk Rekomendasi Produk UMKM Kendari.

Arsitektur: GMF (Generalized Matrix Factorization) dengan BPR Loss
- Menggunakan Bayesian Personalized Ranking (BPR) yang jauh lebih cocok
  untuk data sparse dibanding MSE.
- Negative sampling otomatis saat training.
- Inference menggunakan dot product langsung dari embeddings.

Digunakan setelah user memiliki cukup rating (>= NCF_MIN_RATINGS).
Fallback ke KNN otomatis jika user belum ada di training data.
"""

import os
import numpy as np
import json

os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'

NCF_MODEL_PATH = os.path.join(os.path.dirname(__file__), 'saved_model', 'ncf_model.keras')
NCF_MAPPINGS_PATH = os.path.join(os.path.dirname(__file__), 'ncf_mappings.json')


# ── Negative Sampling ──────────────────────────────────────────────────────────

def prepare_bpr_pairs(ratings_data, n_negatives=4):
    """
    Buat BPR training pairs: (user, item_positif, item_negatif).

    Untuk setiap rating positif, sample n_negatives item yang belum pernah
    dirating user tersebut sebagai negatif.

    Args:
        ratings_data : list of dict {'user_id', 'produk_id', 'score'}
        n_negatives  : jumlah negatif per positif (default 4)

    Returns:
        tuple: (users_pos, items_pos, users_neg, items_neg) — semua list int index
    """
    # Kumpulkan semua produk yang pernah dirating (universe)
    all_produk = list(set(r['produk_id'] for r in ratings_data))

    # Produk yang sudah dirating per user
    rated_per_user = {}
    for r in ratings_data:
        uid = r['user_id']
        pid = r['produk_id']
        rated_per_user.setdefault(uid, set()).add(pid)

    users_pos, items_pos, users_neg, items_neg = [], [], [], []

    for r in ratings_data:
        uid = r['user_id']
        pid = r['produk_id']

        # Kandidat negatif: produk yang belum dirating user ini
        neg_candidates = [p for p in all_produk if p not in rated_per_user[uid]]
        if not neg_candidates:
            continue

        n_sample = min(n_negatives, len(neg_candidates))
        sampled  = np.random.choice(neg_candidates, size=n_sample, replace=False)

        for neg_pid in sampled:
            users_pos.append(uid)
            items_pos.append(pid)
            users_neg.append(uid)
            items_neg.append(neg_pid)

    return users_pos, items_pos, users_neg, items_neg


# ── Model Architecture ─────────────────────────────────────────────────────────

def build_ncf_model(n_users, n_products, embedding_dim=32):
    """
    Bangun model NCF dengan BPR loss (GMF — dot product).

    Embedding dim dikecilkan ke 32 karena data relatif kecil.
    Arsitektur lebih sederhana (tanpa MLP) agar tidak overfit.

    Input saat training : [user_idx, pos_item_idx, neg_item_idx]
    Output              : sigmoid(score_pos - score_neg) → target selalu 1

    Args:
        n_users      : jumlah user unik
        n_products   : jumlah produk unik
        embedding_dim: dimensi embedding (default 32)

    Returns:
        model: Keras model siap compile
    """
    try:
        import tensorflow as tf
        from tensorflow import keras
        from tensorflow.keras import layers
    except ImportError:
        print("TensorFlow tidak tersedia. NCF tidak dapat digunakan.")
        return None

    user_input = keras.Input(shape=(1,), name='user_input')
    pos_input  = keras.Input(shape=(1,), name='pos_input')
    neg_input  = keras.Input(shape=(1,), name='neg_input')

    # Shared embedding layers
    user_emb_layer = layers.Embedding(
        n_users, embedding_dim,
        embeddings_regularizer=tf.keras.regularizers.l2(0.001),
        name='user_emb'
    )
    item_emb_layer = layers.Embedding(
        n_products, embedding_dim,
        embeddings_regularizer=tf.keras.regularizers.l2(0.001),
        name='item_emb'
    )

    user_vec = layers.Flatten()(user_emb_layer(user_input))   # (batch, emb_dim)
    pos_vec  = layers.Flatten()(item_emb_layer(pos_input))    # (batch, emb_dim)
    neg_vec  = layers.Flatten()(item_emb_layer(neg_input))    # (batch, emb_dim)

    # Score = dot product (GMF)
    pos_score = layers.Dot(axes=1, name='pos_score')([user_vec, pos_vec])  # (batch, 1)
    neg_score = layers.Dot(axes=1, name='neg_score')([user_vec, neg_vec])  # (batch, 1)

    # BPR: sigmoid(pos_score - neg_score)
    # Target akan selalu 1.0 → model belajar pos_score > neg_score
    diff   = layers.Subtract(name='bpr_diff')([pos_score, neg_score])
    output = layers.Activation('sigmoid', name='bpr_output')(diff)

    model = keras.Model(
        inputs=[user_input, pos_input, neg_input],
        outputs=output
    )
    model.compile(
        optimizer=keras.optimizers.Adam(learning_rate=0.001),
        loss='binary_crossentropy',   # BPR loss via BCE dengan target=1
        metrics=['accuracy']
    )

    return model


# ── Training ───────────────────────────────────────────────────────────────────

def train_ncf_model(ratings_data, epochs=100):
    """
    Training model NCF-BPR dengan data rating dari database.

    Langkah:
    1. Buat BPR pairs (positif + negatif sampling)
    2. Build model GMF dengan shared embeddings
    3. Train dengan BPR loss (binary_crossentropy, target=1)
    4. Simpan model dan mappings ke disk

    Args:
        ratings_data: list of dict {'user_id', 'produk_id', 'score'}
        epochs      : maksimum epoch (early stopping aktif)

    Returns:
        dict: {'success', 'message', 'n_users', 'n_products', 'n_ratings', 'n_pairs', 'epochs'}
    """
    from config import NCF_MIN_RATINGS

    if not ratings_data or len(ratings_data) < NCF_MIN_RATINGS:
        return {
            'success': False,
            'message': (
                f'Data rating tidak cukup '
                f'(minimal {NCF_MIN_RATINGS}, saat ini {len(ratings_data or [])})'
            )
        }

    try:
        import tensorflow as tf
        from tensorflow.keras.callbacks import EarlyStopping, ReduceLROnPlateau
    except ImportError:
        return {'success': False, 'message': 'TensorFlow tidak tersedia'}

    # ── Mapping ID ke index kontinu ────────────────────────────────────────────
    user_ids   = sorted(set(r['user_id']   for r in ratings_data))
    produk_ids = sorted(set(r['produk_id'] for r in ratings_data))

    user_to_idx   = {uid: i for i, uid in enumerate(user_ids)}
    produk_to_idx = {pid: i for i, pid in enumerate(produk_ids)}

    n_users    = len(user_ids)
    n_products = len(produk_ids)

    # ── BPR Pairs ──────────────────────────────────────────────────────────────
    users_pos, items_pos, users_neg, items_neg = prepare_bpr_pairs(
        ratings_data, n_negatives=4
    )

    if not users_pos:
        return {
            'success': False,
            'message': 'Tidak cukup variasi data untuk BPR training'
        }

    u_arr   = np.array([user_to_idx[u]   for u in users_pos], dtype=np.int32)
    p_arr   = np.array([produk_to_idx[p] for p in items_pos], dtype=np.int32)
    n_arr   = np.array([produk_to_idx[p] for p in items_neg], dtype=np.int32)
    targets = np.ones(len(u_arr), dtype=np.float32)  # BPR: selalu 1

    # ── Build & Train ──────────────────────────────────────────────────────────
    model = build_ncf_model(n_users, n_products)
    if model is None:
        return {'success': False, 'message': 'Gagal membuat model'}

    callbacks = [
        EarlyStopping(
            monitor='loss',
            patience=10,
            restore_best_weights=True,
            verbose=0
        ),
        ReduceLROnPlateau(
            monitor='loss',
            factor=0.5,
            patience=5,
            min_lr=1e-5,
            verbose=0
        )
    ]

    history = model.fit(
        [u_arr, p_arr, n_arr],
        targets,
        epochs=epochs,
        batch_size=32,
        callbacks=callbacks,
        verbose=0
    )

    actual_epochs = len(history.history['loss'])
    final_loss    = history.history['loss'][-1]
    final_acc     = history.history['accuracy'][-1]

    # ── Simpan Model & Mappings ────────────────────────────────────────────────
    os.makedirs(os.path.dirname(NCF_MODEL_PATH), exist_ok=True)
    model.save(NCF_MODEL_PATH)

    mappings = {
        'user_to_idx':   {str(k): v for k, v in user_to_idx.items()},
        'produk_to_idx': {str(k): v for k, v in produk_to_idx.items()},
        'idx_to_produk': {str(v): k for k, v in produk_to_idx.items()},
        'n_users':    n_users,
        'n_products': n_products
    }
    with open(NCF_MAPPINGS_PATH, 'w') as f:
        json.dump(mappings, f)

    # Invalidate cache
    global _cached_model, _cached_model_mtime
    _cached_model       = None
    _cached_model_mtime = 0

    return {
        'success':    True,
        'message':    (
            f'Training BPR berhasil! '
            f'Loss: {final_loss:.4f}, Acc: {final_acc:.4f} '
            f'({actual_epochs} epochs, {len(u_arr)} pairs)'
        ),
        'n_users':    n_users,
        'n_products': n_products,
        'n_ratings':  len(ratings_data),
        'n_pairs':    len(u_arr),
        'epochs':     actual_epochs
    }


# ── Model Caching ──────────────────────────────────────────────────────────────

_cached_model       = None
_cached_model_mtime = 0


def _get_cached_model():
    """
    Load model NCF dari memory cache.
    Auto-reload jika file model berubah (setelah retrain).
    """
    global _cached_model, _cached_model_mtime

    if not os.path.exists(NCF_MODEL_PATH):
        return None

    try:
        import tensorflow as tf
    except ImportError:
        return None

    mtime = os.path.getmtime(NCF_MODEL_PATH)
    if _cached_model is None or mtime > _cached_model_mtime:
        _cached_model       = tf.keras.models.load_model(NCF_MODEL_PATH)
        _cached_model_mtime = mtime

    return _cached_model


# ── Inference ──────────────────────────────────────────────────────────────────

def _get_embedding_scores(model, user_idx, produk_indices):
    """
    Hitung score user vs setiap produk menggunakan dot product embeddings.

    Tidak butuh item negatif saat inference — cukup ambil
    user_embedding · item_embedding untuk setiap kandidat produk.

    Args:
        model        : Keras model yang sudah diload
        user_idx     : index user (int)
        produk_indices: list index produk yang akan di-score

    Returns:
        np.ndarray: scores shape (len(produk_indices),)
    """
    import tensorflow as tf

    n = len(produk_indices)
    u_arr = np.array([user_idx] * n, dtype=np.int32)
    p_arr = np.array(produk_indices,  dtype=np.int32)

    # Ambil embeddings langsung dari layer
    user_emb_layer = model.get_layer('user_emb')
    item_emb_layer = model.get_layer('item_emb')

    # Predict embedding per batch (lebih efisien dari submodel baru)
    user_vecs = user_emb_layer(u_arr).numpy()  # (n, emb_dim)
    item_vecs = item_emb_layer(p_arr).numpy()  # (n, emb_dim)

    # Dot product per baris
    scores = np.sum(user_vecs * item_vecs, axis=1)  # (n,)
    return scores


def ncf_recommend(user_id, all_produk_ids, rated_produk_ids, n_recommendations=8):
    """
    Rekomendasikan produk menggunakan NCF-BPR.

    Alur:
    1. Cek model & mappings tersedia
    2. Cek user ada di training data → jika tidak, trigger retrain & return []
    3. Filter produk belum dirating & ada di mappings
    4. Hitung score via dot product embeddings
    5. Return top-N produk

    Args:
        user_id          : ID user (int/str)
        all_produk_ids   : semua produk_id di database
        rated_produk_ids : produk_id yang sudah dirating user (set/list)
        n_recommendations: jumlah rekomendasi (default 8)

    Returns:
        list of produk_ids yang direkomendasikan (kosong jika gagal → fallback ke KNN)
    """
    if not os.path.exists(NCF_MODEL_PATH) or not os.path.exists(NCF_MAPPINGS_PATH):
        return []

    # Load mappings
    with open(NCF_MAPPINGS_PATH, 'r') as f:
        mappings = json.load(f)

    user_to_idx   = mappings['user_to_idx']
    produk_to_idx = mappings['produk_to_idx']

    # Cek apakah user ada di training data
    user_key = str(user_id)
    if user_key not in user_to_idx:
        # User baru belum ada di model → trigger retrain background
        try:
            from .engine import _trigger_bg_retrain
            _trigger_bg_retrain()
        except Exception:
            pass
        return []  # Fallback ke KNN

    user_idx = user_to_idx[user_key]

    # Load model dari cache
    model = _get_cached_model()
    if model is None:
        return []

    # Filter: belum dirating & ada di mappings produk
    rated_set   = set(str(pid) for pid in rated_produk_ids)
    candidates  = [
        pid for pid in all_produk_ids
        if str(pid) not in rated_set and str(pid) in produk_to_idx
    ]

    if not candidates:
        return []

    produk_indices = [produk_to_idx[str(pid)] for pid in candidates]

    # Hitung scores
    scores = _get_embedding_scores(model, user_idx, produk_indices)

    # Sort descending → ambil top-N
    sorted_idx    = np.argsort(scores)[::-1]
    recommended   = [candidates[i] for i in sorted_idx[:n_recommendations]]

    return recommended