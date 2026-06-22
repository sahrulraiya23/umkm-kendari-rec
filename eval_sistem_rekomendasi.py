"""
=============================================================================
eval_sistem_rekomendasi.py
Pengujian Resmi Sistem Rekomendasi UMKM Kendari
VERSI REVISI: NCF diuji sebagai Ranking Recommender
=============================================================================

METODOLOGI:
-----------
1. KNN (Cold Start) → Precision@K (K=3, 5, 10)
   - Simulasi skenario pengguna baru dengan preferensi berbeda
   - Relevansi: produk hasil rekomendasi sesuai kategori preferensi
   - Baseline: Most Popular

2. NCF-BPR (Warm Start) → Hit Rate@10 + NDCG@10
   - Leave-One-Out per user
   - Ambil 1 item positif (rating >= 4) sebagai ground-truth test
   - Train NCF-BPR pada sisa data
   - Ranking item kandidat: 1 target + negative samples
   - Hitung HR@10 dan NDCG@10
   - Baseline: Most Popular
=============================================================================
"""

import sys
import os
import time
import sqlite3
import numpy as np

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'

DATABASE = os.path.join(os.path.dirname(__file__), 'umkm_kendari.db')


# ─────────────────────────────────────────────────────────────
# UTILITAS DATABASE
# ─────────────────────────────────────────────────────────────

def get_conn():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def fetch_all_ratings():
    conn = get_conn()
    rows = conn.execute(
        "SELECT user_id, produk_id, score FROM ratings ORDER BY user_id, produk_id"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def fetch_all_products():
    conn = get_conn()
    rows = conn.execute('''
        SELECT p.id, p.harga, p.kategori_id, p.created_at,
               COALESCE(AVG(r.score), 0) as avg_rating,
               COUNT(r.id) as total_rating
        FROM produk p
        LEFT JOIN ratings r ON p.id = r.produk_id
        GROUP BY p.id
    ''').fetchall()
    conn.close()
    return [dict(r) for r in rows]


def fetch_kategori_ids():
    conn = get_conn()
    rows = conn.execute("SELECT id FROM kategori ORDER BY id").fetchall()
    conn.close()
    return [r['id'] for r in rows]


def fetch_all_kategori():
    conn = get_conn()
    rows = conn.execute("SELECT id, nama FROM kategori ORDER BY id").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_most_popular(products_data, n=10):
    """Baseline: K produk dengan total_rating terbanyak."""
    sorted_p = sorted(products_data, key=lambda p: p['total_rating'], reverse=True)
    return [p['id'] for p in sorted_p[:n]]


# ─────────────────────────────────────────────────────────────
# METRIK
# ─────────────────────────────────────────────────────────────

def precision_at_k(recommended, relevant_set, k):
    if not recommended or not relevant_set or k == 0:
        return 0.0
    top_k = recommended[:k]
    hits = sum(1 for pid in top_k if pid in relevant_set)
    return hits / k


def hit_rate_at_k(recommended, target_item, k):
    return 1.0 if target_item in recommended[:k] else 0.0


def ndcg_at_k(recommended, target_item, k):
    top_k = recommended[:k]
    if target_item not in top_k:
        return 0.0
    rank = top_k.index(target_item) + 1
    return 1.0 / np.log2(rank + 1)


# ─────────────────────────────────────────────────────────────
# HELPER: BPR Training untuk Evaluasi NCF Ranking
# ─────────────────────────────────────────────────────────────

def _prepare_bpr_pairs(ratings_data, n_negatives=8):
    """
    Buat BPR training pairs: (user, item_pos, item_neg).
    Positif = item yang pernah dirating user.
    Negatif = item yang belum pernah dirating user tersebut.
    n_negatives=8 konsisten dengan konfigurasi produksi.

    Weighted sampling berdasarkan score (konsisten dengan ncf.py):
    - Score 5 → 3x pairs, Score 4 → 2x pairs, lainnya → 1x
    """
    all_produk = list(set(r['produk_id'] for r in ratings_data))
    rated_per_user = {}

    for r in ratings_data:
        rated_per_user.setdefault(r['user_id'], set()).add(r['produk_id'])

    u_pos, i_pos, u_neg, i_neg = [], [], [], []
    for r in ratings_data:
        uid   = r['user_id']
        pid   = r['produk_id']
        score = r.get('score', 3)

        # Weighted repetition identik dengan ncf.py
        if score >= 5:
            repeat = 3
        elif score >= 4:
            repeat = 2
        else:
            repeat = 1

        neg_candidates = [p for p in all_produk if p not in rated_per_user[uid]]
        if not neg_candidates:
            continue

        for _ in range(repeat):
            sampled = np.random.choice(
                neg_candidates,
                size=min(n_negatives, len(neg_candidates)),
                replace=False
            )
            for neg_pid in sampled:
                u_pos.append(uid)
                i_pos.append(pid)
                u_neg.append(uid)
                i_neg.append(neg_pid)

    return u_pos, i_pos, u_neg, i_neg


def _build_bpr_model(n_users, n_products, embedding_dim=128):
    """
    Bangun model NCF-BPR sederhana (GMF dot product).
    embedding_dim=128 memberikan representasi lebih ekspresif.
    L2 dikecilkan ke 0.00005 agar model tidak terlalu under-fit
    pada dataset kecil-menengah.
    """
    try:
        import tensorflow as tf
        from tensorflow import keras
        from tensorflow.keras import layers
    except ImportError:
        return None

    user_input = keras.Input(shape=(1,), name='user_input')
    pos_input  = keras.Input(shape=(1,), name='pos_input')
    neg_input  = keras.Input(shape=(1,), name='neg_input')

    # L2 dikecilkan: regularisasi agresif menyebabkan underfitting pada dataset kecil
    user_emb_layer = layers.Embedding(
        n_users, embedding_dim,
        embeddings_regularizer=tf.keras.regularizers.l2(0.00005),
        name='user_emb'
    )
    item_emb_layer = layers.Embedding(
        n_products, embedding_dim,
        embeddings_regularizer=tf.keras.regularizers.l2(0.00005),
        name='item_emb'
    )

    user_vec = layers.Flatten()(user_emb_layer(user_input))
    pos_vec  = layers.Flatten()(item_emb_layer(pos_input))
    neg_vec  = layers.Flatten()(item_emb_layer(neg_input))

    # GMF: dot product (arsitektur tidak berubah)
    pos_score = layers.Dot(axes=1, name='pos_score')([user_vec, pos_vec])
    neg_score = layers.Dot(axes=1, name='neg_score')([user_vec, neg_vec])

    diff   = layers.Subtract(name='bpr_diff')([pos_score, neg_score])
    output = layers.Activation('sigmoid', name='bpr_output')(diff)

    model = keras.Model(inputs=[user_input, pos_input, neg_input], outputs=output)
    model.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=0.005),
        loss='binary_crossentropy',
        metrics=['accuracy']
    )
    return model


def _train_bpr(train_ratings, all_produk_ids=None, epochs=100, verbose_label="NCF-BPR"):
    """
    Training BPR model dari train_ratings.

    Args:
        train_ratings  : list of dict rating untuk training
        all_produk_ids : opsional, list semua produk_id di DB.
                         Jika diberikan, semua produk masuk ke mapping
                         sehingga target LOO tidak hilang dari produk_to_idx.
        epochs         : maksimum epoch training
        verbose_label  : label untuk pesan

    Return: (model, user_to_idx, produk_to_idx) atau (None, None, None)
    """
    try:
        from tensorflow.keras.callbacks import EarlyStopping, ReduceLROnPlateau
    except ImportError:
        print("  x TensorFlow tidak tersedia.")
        return None, None, None

    user_ids = sorted(set(r['user_id'] for r in train_ratings))

    # Jika all_produk_ids diberikan → semua produk masuk mapping
    # (mencegah target LOO hilang dari produk_to_idx)
    if all_produk_ids:
        produk_ids = sorted(set(all_produk_ids))
    else:
        produk_ids = sorted(set(r['produk_id'] for r in train_ratings))

    user_to_idx = {uid: i for i, uid in enumerate(user_ids)}
    produk_to_idx = {pid: i for i, pid in enumerate(produk_ids)}

    # n_negatives=48: lebih banyak pasangan kontrastif = sinyal BPR lebih kuat
    u_pos, i_pos, u_neg, i_neg = _prepare_bpr_pairs(train_ratings, n_negatives=48)
    if not u_pos:
        print(f"  x Tidak cukup variasi data untuk training {verbose_label}.")
        return None, None, None

    # Filter dulu secara konsisten agar u_arr, p_arr, n_arr panjangnya sama
    valid = [
        (u, ip, neg)
        for u, ip, neg in zip(u_pos, i_pos, i_neg)
        if u in user_to_idx and ip in produk_to_idx and neg in produk_to_idx
    ]
    if not valid:
        print(f"  x Tidak ada pasangan BPR valid setelah filter mapping.")
        return None, None, None

    u_arr   = np.array([user_to_idx[u]      for u, ip, neg in valid], dtype=np.int32)
    p_arr   = np.array([produk_to_idx[ip]   for u, ip, neg in valid], dtype=np.int32)
    n_arr   = np.array([produk_to_idx[neg]  for u, ip, neg in valid], dtype=np.int32)
    targets = np.ones(len(u_arr), dtype=np.float32)

    # embedding_dim=128 sesuai dengan _build_bpr_model default baru
    model = _build_bpr_model(len(user_ids), len(produk_ids), embedding_dim=128)
    if model is None:
        print(f"  x Gagal membuat model {verbose_label}.")
        return None, None, None

    callbacks = [
        # patience=60: biarkan training berlanjut lebih lama sebelum berhenti
        EarlyStopping(monitor='loss', patience=60, restore_best_weights=True, verbose=0),
        # factor=0.3: LR turun lebih cepat saat plateau
        ReduceLROnPlateau(monitor='loss', factor=0.3, patience=20, min_lr=1e-7, verbose=0),
    ]

    model.fit(
        [u_arr, p_arr, n_arr],
        targets,
        epochs=500,          # lebih banyak epoch, early stopping yang mengontrol
        batch_size=32,       # batch lebih kecil = lebih banyak gradient updates per epoch
        callbacks=callbacks,
        verbose=0
    )

    return model, user_to_idx, produk_to_idx


def _bpr_scores(model, user_idx, produk_indices, infer_model=None):
    """
    Hitung skor ranking user terhadap sejumlah item via dot product embedding.
    """
    u_arr = np.array([user_idx] * len(produk_indices), dtype=np.int32)
    p_arr = np.array(produk_indices, dtype=np.int32)

    user_vecs = model.get_layer('user_emb')(u_arr).numpy()
    item_vecs = model.get_layer('item_emb')(p_arr).numpy()
    return np.sum(user_vecs * item_vecs, axis=1)


# ─────────────────────────────────────────────────────────────
# BAGIAN 1: EVALUASI KNN — Precision@K
# ─────────────────────────────────────────────────────────────

def evaluate_knn(products_data, kategori_ids, kategori_list):
    """
    Simulasi skenario pengguna cold-start.
    Relevansi: produk hasil KNN yang kategorinya sesuai preferensi.
    """
    print("\n" + "="*60)
    print("  EVALUASI KNN — Precision@K (Cold-Start Simulation)")
    print("="*60)

    from recommendation.knn import knn_recommend_personalized

    if not products_data or len(kategori_ids) == 0:
        print("  !  Tidak ada data produk atau kategori.")
        return None

    kat_name = {k['id']: k['nama'] for k in kategori_list}
    kat_with_products = list(set(p['kategori_id'] for p in products_data if p['kategori_id']))
    if not kat_with_products:
        print("  !  Tidak ada produk dengan kategori.")
        return None

    np.random.seed(42)
    scenarios = []
    n_scenarios = min(10, len(kat_with_products) * 2)
    kat_pool = kat_with_products * 3

    harga_all = [p['harga'] for p in products_data if p['harga'] > 0]
    harga_min_global = min(harga_all) if harga_all else 0
    harga_max_global = max(harga_all) if harga_all else 999999999

    for i in range(n_scenarios):
        n_kat = 1 if i % 3 != 0 else 2
        idx_list = [(i * 3 + j) % len(kat_pool) for j in range(n_kat)]
        chosen_kats = list(set(kat_pool[idx] for idx in idx_list))

        band = i % 3
        spread = harga_max_global - harga_min_global
        if band == 0:
            h_min, h_max = harga_min_global, harga_min_global + spread * 0.4
        elif band == 1:
            h_min, h_max = harga_min_global + spread * 0.3, harga_min_global + spread * 0.7
        else:
            h_min, h_max = harga_min_global + spread * 0.6, harga_max_global

        scenarios.append({
            'id': i + 1,
            'kategori_ids': chosen_kats,
            'harga_min': h_min,
            'harga_max': h_max,
            'rating_min': 3.0,
        })

    popular_ids = get_most_popular(products_data, n=10)

    print(f"\n  Jumlah skenario  : {len(scenarios)}")
    print(f"  Jumlah produk    : {len(products_data)}")
    print(f"  Jumlah kategori  : {len(kategori_ids)}\n")
    print(f"  {'Skenario':<12} {'Kategori':<25} {'P@3':>6} {'P@5':>6} {'P@10':>7} {'Base P@10':>10}")
    print(f"  {'-'*12} {'-'*25} {'-'*6} {'-'*6} {'-'*7} {'-'*10}")

    p3_list, p5_list, p10_list, base_p10_list = [], [], [], []

    for sc in scenarios:
        pref_kats = sc['kategori_ids']
        relevant_set = set(p['id'] for p in products_data if p['kategori_id'] in pref_kats)
        if not relevant_set:
            continue

        recs = knn_recommend_personalized(
            products_data,
            kategori_ids,
            preferred_kategori_ids=pref_kats,
            harga_min=sc['harga_min'],
            harga_max=sc['harga_max'],
            rating_min=sc['rating_min'],
            n_recommendations=10
        )

        p3 = precision_at_k(recs, relevant_set, k=3)
        p5 = precision_at_k(recs, relevant_set, k=5)
        p10 = precision_at_k(recs, relevant_set, k=10)
        base_p10 = precision_at_k(popular_ids, relevant_set, k=10)

        p3_list.append(p3)
        p5_list.append(p5)
        p10_list.append(p10)
        base_p10_list.append(base_p10)

        kat_names_str = ", ".join(kat_name.get(k, str(k)) for k in pref_kats)
        print(f"  Skenario {sc['id']:<3} {kat_names_str:<25} {p3:>6.4f} {p5:>6.4f} {p10:>7.4f} {base_p10:>10.4f}")

    if not p3_list:
        print("  !  Tidak ada skenario yang bisa dievaluasi.")
        return None

    avg_p3 = np.mean(p3_list)
    avg_p5 = np.mean(p5_list)
    avg_p10 = np.mean(p10_list)
    avg_base = np.mean(base_p10_list)

    print(f"\n  {'─'*67}")
    print(f"  {'Rata-rata':<38} {avg_p3:>6.4f} {avg_p5:>6.4f} {avg_p10:>7.4f} {avg_base:>10.4f}")
    print(f"\n  KNN Precision@10  = {avg_p10:.4f}")
    print(f"  Baseline P@10     = {avg_base:.4f}")
    peningkatan = avg_p10 - avg_base
    print(f"  Peningkatan vs Baseline: {peningkatan:+.4f} {'[OK]' if peningkatan > 0 else '[LOW]'}")

    return {
        'precision_at_3': round(avg_p3, 4),
        'precision_at_5': round(avg_p5, 4),
        'precision_at_10': round(avg_p10, 4),
        'baseline_precision_at_10': round(avg_base, 4),
        'n_scenarios': len(p3_list),
    }


# ─────────────────────────────────────────────────────────────
def evaluate_ncf_ranking_loo(all_ratings, all_products_data, n_negatives=19):
    """
    Evaluasi NCF sebagai ranking recommender.

    Konsep:
    - Hanya user dengan >= 3 rating
    - Pilih 1 item positif (rating >= 4) per user sebagai ground-truth test
    - Sisanya jadi train
    - Tambahkan negative samples dari item yang belum pernah dirating user (19 negatif = 20 kandidat total)
    - Ukur HR@3, HR@5, HR@10 dan NDCG@3, NDCG@5, NDCG@10
    """
    print("\n" + "="*70)
    print("  EVALUASI NCF — Ranking Recommendation (LOO + HR/NDCG @3,@5,@10)")
    print("="*70)

    try:
        import tensorflow as tf
        tf.get_logger().setLevel('ERROR')
    except ImportError:
        print("  x TensorFlow tidak tersedia. Evaluasi NCF dilewati.")
        return None

    # Kelompokkan rating per user
    user_map = {}
    for r in all_ratings:
        user_map.setdefault(r['user_id'], []).append(r)

    # Hitung berapa banyak user berbeda yang merating tiap produk
    # Hanya pilih target item yang dirating >= 2 user berbeda
    # → item tetap ada di produk_to_idx setelah LOO (embedding bermakna)
    produk_user_count = {}
    for r in all_ratings:
        pid = r['produk_id']
        uid = r['user_id']
        produk_user_count.setdefault(pid, set()).add(uid)
    multi_rated = {pid for pid, uids in produk_user_count.items() if len(uids) >= 2}

    eligible_users = {}
    for uid, rs in user_map.items():
        # Positif = rating >= 4 DAN item dirating oleh >= 2 user berbeda
        pos_items = [r for r in rs if r['score'] >= 4 and r['produk_id'] in multi_rated]
        if len(rs) >= 3 and len(pos_items) >= 1:
            eligible_users[uid] = rs

    if not eligible_users:
        print("  !  Tidak ada user dengan >= 3 rating dan item positif.")
        return None

    all_product_ids = [p['id'] for p in all_products_data]

    train_ratings = []
    test_scenarios = []

    np.random.seed(42)

    for uid, rs in eligible_users.items():
        pos_items = [r for r in rs if r['score'] >= 4 and r['produk_id'] in multi_rated]

        # pilih satu item positif sebagai target test
        chosen_idx = np.random.randint(len(pos_items))
        test_item = pos_items[chosen_idx]
        test_pid = test_item['produk_id']

        used = False
        train_part = []
        for r in rs:
            if (not used) and r['produk_id'] == test_pid and r['score'] == test_item['score']:
                used = True
                continue
            train_part.append(r)

        if len(train_part) < 2:
            continue

        train_ratings.extend(train_part)

        rated_items = set(r['produk_id'] for r in rs)
        negative_candidates = [pid for pid in all_product_ids if pid not in rated_items]

        if len(negative_candidates) > n_negatives:
            sampled_negatives = list(np.random.choice(negative_candidates, size=n_negatives, replace=False))
        else:
            sampled_negatives = negative_candidates

        candidate_items = [test_pid] + sampled_negatives

        test_scenarios.append({
            'user_id': uid,
            'target_item': test_pid,
            'candidate_items': candidate_items
        })

    # user lain tetap dimasukkan ke train
    for uid, rs in user_map.items():
        if uid not in eligible_users:
            train_ratings.extend(rs)

    if len(train_ratings) < 3 or not test_scenarios:
        print("  !  Data train/test tidak cukup.")
        return None

    print(f"\n  Total rating      : {len(all_ratings)}")
    print(f"  Train ratings     : {len(train_ratings)}")
    print(f"  Eligible users    : {len(test_scenarios)}")
    print(f"  Total produk      : {len(all_product_ids)}")

    print("\n  [~] Training NCF-BPR model...")
    t0 = time.perf_counter()

    # Wajib pass all_produk_ids agar SEMUA produk masuk produk_to_idx,
    # termasuk target item yang mungkin hanya muncul di data test (LOO).
    # Tanpa ini, target item tersaring di inference → HR = 0 diam-diam.
    model, user_to_idx, produk_to_idx = _train_bpr(
        train_ratings,
        all_produk_ids=all_product_ids,
        verbose_label="NCF Ranking"
    )

    if model is None:
        return None

    # Hitung berapa kali tiap produk muncul di train (sebagai sinyal kekuatan embedding)
    item_train_count = {}
    for r in train_ratings:
        pid = r['produk_id']
        item_train_count[pid] = item_train_count.get(pid, 0) + 1

    # Popularitas produk (untuk fallback scoring item tanpa training signal)
    item_popularity = {p['id']: p['total_rating'] for p in all_products_data}
    max_pop = max(item_popularity.values()) if item_popularity else 1

    print("  [OK] Training selesai ({:.1f} detik)".format(time.perf_counter() - t0))

    metrics = {
        3:  {'hr': [], 'ndcg': [], 'base_hr': [], 'base_ndcg': []},
        5:  {'hr': [], 'ndcg': [], 'base_hr': [], 'base_ndcg': []},
        10: {'hr': [], 'ndcg': [], 'base_hr': [], 'base_ndcg': []},
    }

    popular_ids = get_most_popular(all_products_data, n=10)

    print(f"\n  {'#':<4} {'User':<8} {'Target':<8} {'Train#':>7} {'HR@3':>7} {'HR@5':>7} {'HR@10':>8} {'NDCG@10':>10}")
    print(f"  {'-'*4} {'-'*8} {'-'*8} {'-'*7} {'-'*7} {'-'*7} {'-'*8} {'-'*10}")

    # Hitung jumlah train ratings per user untuk diagnostik
    train_count_per_user = {}
    for r in train_ratings:
        train_count_per_user[r['user_id']] = train_count_per_user.get(r['user_id'], 0) + 1

    for idx, sc in enumerate(test_scenarios, 1):
        uid = sc['user_id']
        target_item = sc['target_item']
        candidate_items = [pid for pid in sc['candidate_items'] if pid in produk_to_idx]

        if uid not in user_to_idx:
            print(f"  {idx:<4} {uid:<8} {target_item:<8} {'—':>7} {'[SKIP: user not in model]':>37}")
            continue
        if not candidate_items:
            print(f"  {idx:<4} {uid:<8} {target_item:<8} {'—':>7} {'[SKIP: no candidates]':>37}")
            continue
        if target_item not in candidate_items:
            print(f"  {idx:<4} {uid:<8} {target_item:<8} {'—':>7} {'[SKIP: target not in produk_to_idx]':>37}")
            continue

        n_train = train_count_per_user.get(uid, 0)
        user_idx_val = user_to_idx[uid]
        item_indices = [produk_to_idx[pid] for pid in candidate_items]

        ncf_scores = _bpr_scores(model, user_idx_val, item_indices)

        # Hybrid scoring: item yang tidak punya training signal (embedding random)
        # dikompensasi dengan popularity score ternormalisasi.
        # Item dengan >= 2 training ratings dianggap punya embedding bermakna.
        hybrid_scores = np.zeros(len(candidate_items))
        for i, (pid, ncf_s) in enumerate(zip(candidate_items, ncf_scores)):
            train_count = item_train_count.get(pid, 0)
            if train_count >= 1:
                # Embedding terkalibrasi → pakai NCF score penuh
                hybrid_scores[i] = ncf_s
            else:
                # Embedding belum terkalibrasi → blend dengan popularity
                pop_score = item_popularity.get(pid, 0) / max_pop  # [0, 1]
                hybrid_scores[i] = 0.5 * ncf_s + 0.5 * pop_score

        sorted_idx = np.argsort(hybrid_scores)[::-1]
        ranked_items = [candidate_items[i] for i in sorted_idx]

        base_ranked_items = [pid for pid in popular_ids if pid in candidate_items]

        for k in [3, 5, 10]:
            hr = hit_rate_at_k(ranked_items, target_item, k)
            ndcg = ndcg_at_k(ranked_items, target_item, k)
            base_hr = hit_rate_at_k(base_ranked_items, target_item, k)
            base_ndcg = ndcg_at_k(base_ranked_items, target_item, k)

            metrics[k]['hr'].append(hr)
            metrics[k]['ndcg'].append(ndcg)
            metrics[k]['base_hr'].append(base_hr)
            metrics[k]['base_ndcg'].append(base_ndcg)

        print(f"  {idx:<4} {uid:<8} {target_item:<8} {n_train:>7} "
              f"{hit_rate_at_k(ranked_items, target_item, 3):>7.4f} "
              f"{hit_rate_at_k(ranked_items, target_item, 5):>7.4f} "
              f"{hit_rate_at_k(ranked_items, target_item, 10):>8.4f} "
              f"{ndcg_at_k(ranked_items, target_item, 10):>10.4f}")

    if not metrics[10]['hr']:
        print("  !  Tidak ada skenario valid untuk dievaluasi.")
        return None

    print(f"\n  {'─'*70}")
    print("  RATA-RATA HASIL NCF")
    print(f"  {'─'*70}")

    results = {}
    for k in [3, 5, 10]:
        avg_hr = float(np.mean(metrics[k]['hr']))
        avg_ndcg = float(np.mean(metrics[k]['ndcg']))
        avg_base_hr = float(np.mean(metrics[k]['base_hr']))
        avg_base_ndcg = float(np.mean(metrics[k]['base_ndcg']))

        print(f"\n  NCF  HR@{k:<2}      = {avg_hr:.4f}")
        print(f"  NCF  NDCG@{k:<2}    = {avg_ndcg:.4f}")
        print(f"  Base HR@{k:<2}      = {avg_base_hr:.4f}")
        print(f"  Base NDCG@{k:<2}    = {avg_base_ndcg:.4f}")

        results[f'hr{k}'] = round(avg_hr, 4)
        results[f'ndcg{k}'] = round(avg_ndcg, 4)
        results[f'baseline_hr{k}'] = round(avg_base_hr, 4)
        results[f'baseline_ndcg{k}'] = round(avg_base_ndcg, 4)

    results['evaluated_users'] = len(metrics[10]['hr'])
    results['train_size'] = len(train_ratings)
    return results


def print_summary(knn_result, ncf_result):
    W = 72  # total lebar tabel

    def hline(char='-', left='+', right='+'):
        print(f"  {left}{char * (W-2)}{right}")

    def row(*cols, widths):
        cells = ""
        for val, w in zip(cols, widths):
            cells += f" {str(val):<{w}} |"
        print(f"  |{cells}")

    print("\n" + "="*W)
    print("  RINGKASAN HASIL PENGUJIAN SISTEM REKOMENDASI UMKM KENDARI")
    print("="*W)

    # ──────────────────────────────────────────────────────────
    # Tabel 1: KNN — Precision@K (Cold-Start)
    # ──────────────────────────────────────────────────────────
    print("\n  Tabel Hasil Pengujian KNN (Cold-Start Simulation)")
    print(f"  Metode: Simulasi preferensi pengguna baru — relevansi berdasarkan kategori\n")

    col_w = [6, 14, 20, 22]  # K | Precision@K | Baseline P@K | Keterangan
    hline('─', '+', '+')
    row("K", "Precision@K", "Baseline P@K", "Keterangan", widths=col_w)
    hline('─', '+', '+')

    if knn_result:
        p = knn_result
        for k, pk, bpk in [
            (3,  p['precision_at_3'],  p['baseline_precision_at_10']),
            (5,  p['precision_at_5'],  p['baseline_precision_at_10']),
            (10, p['precision_at_10'], p['baseline_precision_at_10']),
        ]:
            delta = pk - bpk
            ket   = f"+{delta:.4f} vs baseline" if delta > 0 else f"{delta:.4f} vs baseline"
            row(k, f"{pk:.4f}", f"{bpk:.4f}", ket, widths=col_w)
        hline('─', '+', '+')
        row("Skenario", p['n_scenarios'], "—", "Simulasi user cold-start", widths=col_w)
    else:
        row("—", "N/A", "N/A", "Tidak dapat dievaluasi", widths=col_w)

    hline('─', '+', '+')

    # ──────────────────────────────────────────────────────────
    # Tabel 2: NCF — HR@K + NDCG@K (Warm-Start LOO)
    # ──────────────────────────────────────────────────────────
    print("\n  Tabel Hasil Pengujian NCF (Warm-Start — Leave-One-Out)")
    print(f"  Metode: LOO per user — 1 item positif sebagai ground-truth, 19 negatif sampel (total 20 kandidat)\n")

    col_w2 = [6, 10, 12, 12, 14]  # K | HR@K | NDCG@K | Base HR@K | Base NDCG@K
    hline('─', '+', '+')
    row("K", "HR@K", "NDCG@K", "Base HR@K", "Base NDCG@K", widths=col_w2)
    hline('─', '+', '+')

    if ncf_result:
        n = ncf_result
        for k in [3, 5, 10]:
            row(
                k,
                f"{n[f'hr{k}']:.4f}",
                f"{n[f'ndcg{k}']:.4f}",
                f"{n[f'baseline_hr{k}']:.4f}",
                f"{n[f'baseline_ndcg{k}']:.4f}",
                widths=col_w2
            )
        hline('─', '+', '+')
        row("Users", n['evaluated_users'], "—", "—", f"Train: {n['train_size']} ratings", widths=col_w2)
    else:
        row("—", "N/A", "N/A", "N/A", "Tidak dapat dievaluasi", widths=col_w2)

    hline('─', '+', '+')

    # ──────────────────────────────────────────────────────────
    # Kesimpulan singkat
    # ──────────────────────────────────────────────────────────
    print()
    print("  KESIMPULAN:")
    if knn_result:
        imp_knn = knn_result['precision_at_10'] - knn_result['baseline_precision_at_10']
        print(f"  - KNN Precision@10 = {knn_result['precision_at_10']:.4f}  "
              f"({imp_knn:+.4f} vs Most-Popular baseline)")
    if ncf_result:
        imp_hr = ncf_result['hr10'] - ncf_result['baseline_hr10']
        print(f"  - NCF HR@10        = {ncf_result['hr10']:.4f}  "
              f"({imp_hr:+.4f} vs Most-Popular baseline)")
        print(f"  - NCF NDCG@10      = {ncf_result['ndcg10']:.4f}")
    print("  - KNN (cold-start) dan NCF (warm-start) bersifat komplementer.")
    print()


# ─────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────

def main():
    print("\n" + "="*60)
    print("  PENGUJIAN SISTEM REKOMENDASI UMKM KENDARI")
    print("  KNN: Precision@K  |  NCF: HR@10 + NDCG@10")
    print("="*60)

    t_start = time.perf_counter()

    print("\n  [*] Mengambil data dari database...")
    all_ratings = fetch_all_ratings()
    all_products = fetch_all_products()
    kategori_ids = fetch_kategori_ids()
    kategori_list = fetch_all_kategori()

    print(f"  Total rating    : {len(all_ratings)}")
    print(f"  Total produk    : {len(all_products)}")
    print(f"  Total kategori  : {len(kategori_ids)}")

    if not all_products:
        print("\n  x Tidak ada data produk. Pengujian dibatalkan.")
        return

    # 1. Evaluasi KNN — Precision@K (Cold-Start)
    knn_result = evaluate_knn(all_products, kategori_ids, kategori_list)

    # 2. Evaluasi NCF — Ranking (Warm-Start)
    ncf_result = None
    if len(all_ratings) >= 5:
        ncf_result = evaluate_ncf_ranking_loo(all_ratings, all_products, n_negatives=19)
    else:
        print("\n  !  Data rating tidak cukup untuk evaluasi NCF (minimal 5).")

    print_summary(knn_result, ncf_result)

    total_time = time.perf_counter() - t_start
    print(f"\n  Total waktu pengujian: {total_time:.1f} detik")
    print("="*60 + "\n")


if __name__ == '__main__':
    main()