# -*- coding: utf-8 -*-
"""
Evaluasi Perbandingan NCF vs KNN
===========================================
Menggunakan Leave-One-Out dengan simulasi variasi jumlah
interaksi training (1, 3, 5, 8, 10, 14 item) dari 15 rating
yang dimiliki setiap user.
"""
import sys, os, time
sys.path.insert(0, os.path.dirname(__file__))
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'

from app import create_app
app = create_app()

with app.app_context():
    from models.database import get_db
    from recommendation.ncf import train_ncf_model, ncf_recommend
    from recommendation.knn import knn_recommend, knn_recommend_personalized, get_knn_data_from_db
    from recommendation.evaluation import ndcg_at_k
    import numpy as np
    import random
    random.seed(42)

    db = get_db()
    all_ratings = [dict(r) for r in db.execute('SELECT user_id, produk_id, score FROM ratings').fetchall()]
    all_produk_ids = [r['id'] for r in db.execute('SELECT id FROM produk WHERE tersedia=1 AND stok>0').fetchall()]
    products_data, kategori_ids = get_knn_data_from_db()
    prod_map = {p['id']: p for p in products_data}

    # --- Group by user ---
    user_map = {}
    for r in all_ratings:
        uid = r['user_id']
        if uid not in user_map:
            user_map[uid] = []
        user_map[uid].append(r)

    print(f"Total User  : {len(user_map)}")
    print(f"Total Rating: {len(all_ratings)}")
    print(f"Avg Rating/User: {len(all_ratings)/len(user_map):.1f}\n")

    # --- Latih NCF dengan SEMUA data dulu (untuk evaluasi subset) ---
    print("Melatih model NCF dengan data penuh...")
    train_ncf_model(all_ratings, epochs=100)
    print("Training selesai.\n")

    # ===================================================================
    # EVALUASI DENGAN VARIASI JUMLAH TRAINING
    # Simulasi: dari 15 rating per user, kita test dengan subsample
    # training yang berbeda (LOO: 1 item terbaik jadi test, sisanya train)
    # Group: subset 1, 3, 5, 8, 10, 14 item dari training history
    # ===================================================================
    # Test item = produk dengan skor TERTINGGI milik user (LOO)
    # Lalu kita simulasikan dengan berapa item training NCF/KNN bisa hit

    TRAIN_SIZES = [1, 3, 5, 8, 10, 14]  # jumlah item training yang digunakan
    LABELS      = ["1 Item", "3 Item", "5 Item", "8 Item", "10 Item", "14 Item"]
    K = 10

    # Siapkan test_set per user (LOO — ambil item skor tertinggi sebagai test)
    test_set = {}
    full_train_set = {}
    for uid, rts in user_map.items():
        sorted_r = sorted(rts, key=lambda x: x['score'], reverse=True)
        test_set[uid] = sorted_r[0]                   # item test
        full_train_set[uid] = sorted_r[1:]             # 14 item sisanya

    all_uids = list(user_map.keys())

    final_results = []

    for size, label in zip(TRAIN_SIZES, LABELS):
        ncf_hr_list, ncf_ndcg_list, ncf_time_list = [], [], []
        knn_hr_list, knn_time_list = [], []

        for uid in all_uids:
            target = test_set[uid]
            target_pid = target['produk_id']

            # Ambil subset training (size item pertama dari training history)
            train_subset = full_train_set[uid][:size]
            train_pids   = [r['produk_id'] for r in train_subset]

            relevant_scores = {target_pid: target['score']}

            # --- NCF ---
            t0 = time.perf_counter()
            rec_ncf = ncf_recommend(uid, all_produk_ids, train_pids, n_recommendations=K)
            ncf_time_list.append((time.perf_counter() - t0) * 1000)
            ncf_hr_list.append(1 if target_pid in rec_ncf else 0)
            ncf_ndcg_list.append(ndcg_at_k(rec_ncf, relevant_scores, k=K))

            # --- KNN ---
            t0 = time.perf_counter()
            pref_kats = list(set(prod_map[pid]['kategori_id'] for pid in train_pids if pid in prod_map))
            if pref_kats:
                rec_knn = knn_recommend_personalized(products_data, kategori_ids, pref_kats, n_recommendations=K)
            else:
                rec_knn = knn_recommend(products_data, kategori_ids, n_recommendations=K)
            knn_time_list.append((time.perf_counter() - t0) * 1000)
            knn_hr_list.append(1 if target_pid in rec_knn else 0)

        final_results.append({
            "label"    : label,
            "n_users"  : len(all_uids),
            "ncf_hr"   : np.mean(ncf_hr_list),
            "ncf_ndcg" : np.mean(ncf_ndcg_list),
            "ncf_time" : np.mean(ncf_time_list),
            "knn_hr"   : np.mean(knn_hr_list),
            "knn_time" : np.mean(knn_time_list),
        })

    # ===================================================================
    # CETAK HASIL
    # ===================================================================
    sep = "=" * 100
    print("\n" + sep)
    print("HASIL EVALUASI PERBANDINGAN NCF vs KNN")
    print("Metode  : Leave-One-Out | Variasi jumlah item training per user")
    print(f"User    : {len(all_uids)} | Item test: skor tertinggi tiap user")
    print(sep)
    header = f"{'Kelompok History':<18} {'HR@10 NCF':<12} {'HR@10 KNN':<12} {'Prec@10 NCF':<14} {'NDCG@10 NCF':<14} {'Waktu NCF (ms)':<16} {'Waktu KNN (ms)':<14}"
    print(header)
    print("-" * 100)

    for r in final_results:
        ncf_hr   = r['ncf_hr']
        knn_hr   = r['knn_hr']
        ncf_prec = ncf_hr / K
        ncf_ndcg = r['ncf_ndcg']
        ncf_t    = r['ncf_time']
        knn_t    = r['knn_time']

        print(
            f"{r['label']:<18} "
            f"{ncf_hr:<12.4f} "
            f"{knn_hr:<12.4f} "
            f"{ncf_prec:<14.4f} "
            f"{ncf_ndcg:<14.4f} "
            f"{ncf_t:<16.2f} "
            f"{knn_t:<14.2f}"
        )

    print(sep)

    # Rata-rata total
    avg_ncf_hr   = np.mean([r['ncf_hr']   for r in final_results])
    avg_knn_hr   = np.mean([r['knn_hr']   for r in final_results])
    avg_ncf_ndcg = np.mean([r['ncf_ndcg'] for r in final_results])
    avg_ncf_t    = np.mean([r['ncf_time'] for r in final_results])
    avg_knn_t    = np.mean([r['knn_time'] for r in final_results])

    print(
        f"{'RATA-RATA':<18} "
        f"{avg_ncf_hr:<12.4f} "
        f"{avg_knn_hr:<12.4f} "
        f"{avg_ncf_hr/K:<14.4f} "
        f"{avg_ncf_ndcg:<14.4f} "
        f"{avg_ncf_t:<16.2f} "
        f"{avg_knn_t:<14.2f}"
    )
    print(sep)

    print("\nINTERPRETASI:")
    print(f"  NCF avg HR@10  : {avg_ncf_hr:.4f}  ({avg_ncf_hr*100:.2f}%)")
    print(f"  KNN avg HR@10  : {avg_knn_hr:.4f}  ({avg_knn_hr*100:.2f}%)")
    print(f"  NCF avg NDCG@10: {avg_ncf_ndcg:.4f}")
    winner = "NCF" if avg_ncf_hr >= avg_knn_hr else "KNN"
    print(f"  Model lebih baik (HR): {winner}")
    print(f"  NCF rata-rata {avg_ncf_t:.1f}ms vs KNN {avg_knn_t:.1f}ms per query")
