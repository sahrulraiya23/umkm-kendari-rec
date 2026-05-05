"""
=============================================================================
eval_tabel_akademik.py
Pengujian Akademik — Output format tabel sesuai laporan skripsi
=============================================================================

Menghasilkan 2 tabel:

  Tabel 1 — KNN (Cold-Start):
    K | Precision@K | Recall@K | F1-Score@K | Avg. Response Time (ms) | Coverage

  Tabel 2 — NCF (Warm-Start, per segmen pengguna):
    Segmen Pengguna | HR@10 | NDCG@10 | MAE | Avg. Inference Time (ms)

Tidak mengubah logika di knn.py / ncf.py sama sekali.
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
# DATABASE HELPERS
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
        SELECT p.id, p.harga, p.kategori_id,
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


# ─────────────────────────────────────────────────────────────
# TABEL 1: KNN — Precision@K, Recall@K, F1@K, Time, Coverage
# ─────────────────────────────────────────────────────────────

def run_knn_tabel(products_data, kategori_ids, kategori_list, k_values=(3, 5, 10, 20)):
    """
    Simulasi cold-start untuk berbagai nilai K.
    Menghasilkan: Precision@K, Recall@K, F1@K, Avg Response Time, Coverage.

    Recall@K = |relevant ∩ rekomendasi@K| / |total relevan|
    Coverage = |unique item direkomendasikan| / |total produk|
    """
    from recommendation.knn import knn_recommend_personalized

    print("\n" + "=" * 75)
    print("  TABEL 1 — Hasil Pengujian KNN (Cold-Start Simulation)")
    print("=" * 75)
    print("  Metode: Simulasi preferensi pengguna baru, relevansi = kategori\n")

    kat_name = {k['id']: k['nama'] for k in kategori_list}
    kat_with_products = list(set(p['kategori_id'] for p in products_data if p['kategori_id']))
    if not kat_with_products:
        print("  ! Tidak ada produk berkategori.")
        return

    # Buat 10 skenario simulasi deterministik
    np.random.seed(42)
    n_scenarios = min(10, len(kat_with_products) * 2)
    kat_pool = kat_with_products * 3
    harga_all = [p['harga'] for p in products_data if p['harga'] > 0]
    h_min_g = min(harga_all) if harga_all else 0
    h_max_g = max(harga_all) if harga_all else 999999

    scenarios = []
    for i in range(n_scenarios):
        n_kat = 1 if i % 3 != 0 else 2
        chosen_kats = list(set(kat_pool[(i * 3 + j) % len(kat_pool)] for j in range(n_kat)))
        band = i % 3
        spread = h_max_g - h_min_g
        if band == 0:
            h_min, h_max = h_min_g, h_min_g + spread * 0.4
        elif band == 1:
            h_min, h_max = h_min_g + spread * 0.3, h_min_g + spread * 0.7
        else:
            h_min, h_max = h_min_g + spread * 0.6, h_max_g
        scenarios.append({
            'id': i + 1,
            'kategori_ids': chosen_kats,
            'harga_min': h_min,
            'harga_max': h_max,
            'rating_min': 3.0,
        })

    max_k = max(k_values)
    all_product_ids = set(p['id'] for p in products_data)

    # Kumpulkan metrik per K
    results = {k: {'precision': [], 'recall': [], 'f1': [], 'time_ms': [], 'covered': set()} for k in k_values}

    for sc in scenarios:
        pref_kats = sc['kategori_ids']
        relevant_set = set(p['id'] for p in products_data if p['kategori_id'] in pref_kats)
        if not relevant_set:
            continue

        t0 = time.perf_counter()
        recs = knn_recommend_personalized(
            products_data,
            kategori_ids,
            preferred_kategori_ids=pref_kats,
            harga_min=sc['harga_min'],
            harga_max=sc['harga_max'],
            rating_min=sc['rating_min'],
            n_recommendations=max_k
        )
        elapsed_ms = (time.perf_counter() - t0) * 1000

        for k in k_values:
            top_k = recs[:k]
            hits = sum(1 for pid in top_k if pid in relevant_set)
            precision = hits / k if k > 0 else 0.0
            recall    = hits / len(relevant_set) if relevant_set else 0.0
            f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0
            results[k]['precision'].append(precision)
            results[k]['recall'].append(recall)
            results[k]['f1'].append(f1)
            results[k]['time_ms'].append(elapsed_ms)
            results[k]['covered'].update(top_k)

    # Cetak tabel
    W = 75
    col_w = [5, 14, 12, 14, 24, 12]

    def hline():
        print("  +" + "-" * (W - 4) + "+")

    def header_row():
        cols = ["K", "Precision@K", "Recall@K", "F1-Score@K", "Avg. Response Time (ms)", "Coverage"]
        cells = ""
        for val, w in zip(cols, col_w):
            cells += f" {str(val):<{w}} |"
        print(f"  |{cells}")

    hline()
    header_row()
    hline()

    for k in k_values:
        r = results[k]
        if not r['precision']:
            continue
        avg_prec = np.mean(r['precision'])
        avg_rec  = np.mean(r['recall'])
        avg_f1   = np.mean(r['f1'])
        avg_time = np.mean(r['time_ms'])
        coverage = len(r['covered']) / len(all_product_ids) if all_product_ids else 0.0

        cols = [k, f"{avg_prec:.4f}", f"{avg_rec:.4f}", f"{avg_f1:.4f}",
                f"{avg_time:.2f}", f"{coverage:.4f}"]
        cells = ""
        for val, w in zip(cols, col_w):
            cells += f" {str(val):<{w}} |"
        print(f"  |{cells}")

    hline()
    print(f"  Skenario simulasi : {n_scenarios}")
    print(f"  Total produk      : {len(products_data)}\n")


# ─────────────────────────────────────────────────────────────
# TABEL 2: NCF — HR@10, NDCG@10, MAE, Inference Time
#          Dikelompokkan per segmen pengguna (jumlah rating)
# ─────────────────────────────────────────────────────────────

def _build_ncf_rating_model(n_users, n_products, embedding_dim=32):
    """NCF (GMF + MLP) dengan MSE loss untuk prediksi rating."""
    try:
        import tensorflow as tf
        from tensorflow import keras
        from tensorflow.keras import layers
    except ImportError:
        return None

    user_input = keras.Input(shape=(1,), name='user_input')
    item_input = keras.Input(shape=(1,), name='item_input')

    user_emb = layers.Flatten()(layers.Embedding(
        n_users, embedding_dim,
        embeddings_regularizer=tf.keras.regularizers.l2(0.001), name='user_emb'
    )(user_input))
    item_emb = layers.Flatten()(layers.Embedding(
        n_products, embedding_dim,
        embeddings_regularizer=tf.keras.regularizers.l2(0.001), name='item_emb'
    )(item_input))

    gmf    = layers.Multiply()([user_emb, item_emb])
    concat = layers.Concatenate()([user_emb, item_emb])
    mlp    = layers.Dense(64, activation='relu')(concat)
    mlp    = layers.Dropout(0.2)(mlp)
    mlp    = layers.Dense(32, activation='relu')(mlp)

    combined = layers.Concatenate()([gmf, mlp])
    output   = layers.Dense(1, activation='sigmoid', name='output')(combined)

    model = keras.Model(inputs=[user_input, item_input], outputs=output)
    model.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=0.001),
        loss='mean_squared_error', metrics=['mae']
    )
    return model


def run_ncf_tabel(all_ratings, all_products_data):
    """
    Evaluasi NCF per segmen pengguna berdasarkan jumlah rating.
    Segmen: 1-4 rating | 5-10 rating | >10 rating

    Metrik per segmen:
      HR@10    : apakah item test (rating >= 4) muncul di top-10 prediksi
      NDCG@10  : ranking-aware hit rate
      MAE      : Mean Absolute Error prediksi rating
      Avg. Inference Time (ms)
    """
    print("=" * 75)
    print("  TABEL 2 — Hasil Pengujian NCF (Warm-Start, per Segmen Pengguna)")
    print("=" * 75)
    print("  Metode: 80/20 split per user — HR@10, NDCG@10, MAE, Inference Time\n")

    try:
        import tensorflow as tf
        from tensorflow.keras.callbacks import EarlyStopping, ReduceLROnPlateau
        tf.get_logger().setLevel('ERROR')
    except ImportError:
        print("  ! TensorFlow tidak tersedia.")
        return

    if len(all_ratings) < 5:
        print("  ! Data rating terlalu sedikit.")
        return

    # ── Split 80/20 per user ──
    user_map = {}
    for r in all_ratings:
        user_map.setdefault(r['user_id'], []).append(r)

    np.random.seed(42)
    train_ratings = []
    test_scenarios = []   # (uid, test_items_dict, n_user_ratings)

    for uid, user_rs in user_map.items():
        shuffled = sorted(user_rs, key=lambda x: x['produk_id'])
        n_train  = max(1, int(len(shuffled) * 0.8))
        train_ratings.extend(shuffled[:n_train])
        if len(shuffled) > 1:
            test_items = {r['produk_id']: r['score'] for r in shuffled[n_train:]}
            if test_items:
                test_scenarios.append((uid, test_items, len(user_rs)))

    if not test_scenarios:
        print("  ! Tidak ada data test.")
        return

    # ── Mapping ──
    user_ids   = sorted(set(r['user_id']   for r in train_ratings))
    produk_ids = sorted(set(r['produk_id'] for r in train_ratings))
    user_to_idx   = {uid: i for i, uid in enumerate(user_ids)}
    produk_to_idx = {pid: i for i, pid in enumerate(produk_ids)}

    n_users    = len(user_ids)
    n_products = len(produk_ids)

    # ── Training ──
    print("  [~] Training NCF model...")
    t0 = time.perf_counter()

    u_train = np.array([user_to_idx[r['user_id']]     for r in train_ratings], dtype=np.int32)
    p_train = np.array([produk_to_idx[r['produk_id']] for r in train_ratings], dtype=np.int32)
    y_train = np.array([r['score'] for r in train_ratings], dtype=np.float32) / 5.0

    model = _build_ncf_rating_model(n_users, n_products, embedding_dim=32)
    if model is None:
        print("  ! Gagal membuat model NCF.")
        return

    use_val = len(train_ratings) >= 10
    callbacks = [
        EarlyStopping(monitor='val_loss' if use_val else 'loss',
                      patience=12, restore_best_weights=True, verbose=0),
        ReduceLROnPlateau(monitor='val_loss' if use_val else 'loss',
                         factor=0.5, patience=6, min_lr=1e-5, verbose=0),
    ]
    model.fit(
        [u_train, p_train], y_train,
        epochs=150, batch_size=16,
        validation_split=0.15 if use_val else 0.0,
        callbacks=callbacks, verbose=0
    )
    print(f"  [OK] Training selesai ({time.perf_counter() - t0:.1f} detik)\n")

    all_produk_ids = [p['id'] for p in all_products_data]

    # ── Segmentasi ──
    segments = {
        '1–4 Rating':  {'hr': [], 'ndcg': [], 'mae': [], 'time_ms': []},
        '5–10 Rating': {'hr': [], 'ndcg': [], 'mae': [], 'time_ms': []},
        '> 10 Rating': {'hr': [], 'ndcg': [], 'mae': [], 'time_ms': []},
    }

    def get_segment(n):
        if n <= 4:
            return '1–4 Rating'
        elif n <= 10:
            return '5–10 Rating'
        else:
            return '> 10 Rating'

    for uid, test_items, n_user_ratings in test_scenarios:
        if uid not in user_to_idx:
            continue

        seg = get_segment(n_user_ratings)
        user_idx = user_to_idx[uid]
        trained_rated = set(r['produk_id'] for r in train_ratings if r['user_id'] == uid)

        # ── Inference + hitung waktu ──
        valid_pids = [pid for pid in all_produk_ids
                      if pid not in trained_rated and pid in produk_to_idx]
        if not valid_pids:
            continue

        t_infer = time.perf_counter()
        u_arr = np.array([user_idx] * len(valid_pids), dtype=np.int32)
        p_arr = np.array([produk_to_idx[pid] for pid in valid_pids], dtype=np.int32)
        preds_norm = model.predict([u_arr, p_arr], verbose=0).flatten()
        infer_ms   = (time.perf_counter() - t_infer) * 1000

        scores_dict = {pid: float(np.clip(preds_norm[i] * 5.0, 1.0, 5.0))
                       for i, pid in enumerate(valid_pids)}

        sorted_pids = sorted(scores_dict, key=scores_dict.get, reverse=True)
        top10       = sorted_pids[:10]

        # HR@10 : apakah ada item test (score >= 4) di top-10
        rel_items = {pid for pid, sc in test_items.items() if sc >= 4}
        hr10 = 1.0 if any(pid in top10 for pid in rel_items) else 0.0

        # NDCG@10
        ndcg10 = 0.0
        ideal_scores = sorted(test_items.values(), reverse=True)
        idcg = sum(s / np.log2(i + 2) for i, s in enumerate(ideal_scores[:10]))
        for rank_i, pid in enumerate(top10):
            if pid in test_items:
                ndcg10 += test_items[pid] / np.log2(rank_i + 2)
        ndcg10 = ndcg10 / idcg if idcg > 0 else 0.0

        # MAE untuk item test yang ada di valid_pids
        mae_vals = []
        for pid, actual_score in test_items.items():
            if pid in scores_dict:
                mae_vals.append(abs(actual_score - scores_dict[pid]))
        mae = float(np.mean(mae_vals)) if mae_vals else float('nan')

        segments[seg]['hr'].append(hr10)
        segments[seg]['ndcg'].append(ndcg10)
        if not np.isnan(mae):
            segments[seg]['mae'].append(mae)
        segments[seg]['time_ms'].append(infer_ms)

    # ── Cetak Tabel ──
    W = 75
    col_w = [15, 10, 12, 10, 24]

    def hline():
        print("  +" + "-" * (W - 4) + "+")

    def header_row():
        cols = ["Segmen Pengguna", "HR@10", "NDCG@10", "MAE", "Avg. Inference Time (ms)"]
        cells = ""
        for val, w in zip(cols, col_w):
            cells += f" {str(val):<{w}} |"
        print(f"  |{cells}")

    hline()
    header_row()
    hline()

    for seg_name in ['1–4 Rating', '5–10 Rating', '> 10 Rating']:
        d = segments[seg_name]
        if not d['hr']:
            cols = [seg_name, "N/A", "N/A", "N/A", "N/A"]
        else:
            avg_hr   = np.mean(d['hr'])
            avg_ndcg = np.mean(d['ndcg'])
            avg_mae  = np.mean(d['mae']) if d['mae'] else float('nan')
            avg_time = np.mean(d['time_ms'])
            cols = [
                seg_name,
                f"{avg_hr:.4f}",
                f"{avg_ndcg:.4f}",
                f"{avg_mae:.4f}" if not np.isnan(avg_mae) else "N/A",
                f"{avg_time:.2f}",
            ]
        cells = ""
        for val, w in zip(cols, col_w):
            cells += f" {str(val):<{w}} |"
        print(f"  |{cells}")

    hline()
    total_eval = sum(len(d['hr']) for d in segments.values())
    print(f"  Total user dievaluasi : {total_eval}")
    print(f"  Train ratings         : {len(train_ratings)}")
    print(f"  Total produk          : {len(all_products_data)}\n")


# ─────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────

def main():
    print("\n" + "=" * 75)
    print("  PENGUJIAN AKADEMIK — UMKM KENDARI RECOMMENDATION SYSTEM")
    print("  Output: Tabel KNN & NCF sesuai format laporan skripsi")
    print("=" * 75)

    t_start = time.perf_counter()

    conn = get_conn()
    print("\n  [*] Memuat data dari database...")
    all_ratings   = fetch_all_ratings()
    all_products  = fetch_all_products()
    kategori_ids  = fetch_kategori_ids()
    kategori_list = fetch_all_kategori()
    conn.close()

    print(f"  Total rating    : {len(all_ratings)}")
    print(f"  Total produk    : {len(all_products)}")
    print(f"  Total kategori  : {len(kategori_ids)}\n")

    if not all_products:
        print("  x Tidak ada data produk.")
        return

    # ── Tabel 1: KNN ──
    run_knn_tabel(all_products, kategori_ids, kategori_list, k_values=(3, 5, 10, 20))

    # ── Tabel 2: NCF ──
    if len(all_ratings) >= 5:
        run_ncf_tabel(all_ratings, all_products)
    else:
        print("  ! Data rating tidak cukup untuk evaluasi NCF (minimal 5).")

    print(f"  Total waktu pengujian: {time.perf_counter() - t_start:.1f} detik")
    print("=" * 75 + "\n")


if __name__ == '__main__':
    main()
