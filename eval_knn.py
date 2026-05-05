"""
EVALUASI KNN — Leave-One-Out Cross Validation (FIXED)
======================================================
Fix:
  - NDCG: IDCG selalu = 1.0 karena test set = 1 item (bukan min(k, relevant))
  - Guard: skip jika test_kat adalah None
  - HR@K: sekarang dihitung sebagai rata-rata per user (bukan per fold)
"""
import sys, os, time, random, math
import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
random.seed(42)

from app import create_app
app = create_app()

def hitung_ndcg(recs_kats, relevant_kats, k):
    """
    NDCG untuk single-item test set.
    IDCG = 1.0 selalu karena hanya ada 1 item relevan yang mungkin.
    DCG = 1/log2(pos+2) jika kategori relevan ditemukan, else 0.
    """
    for i, kat in enumerate(recs_kats[:k]):
        if kat is not None and kat in relevant_kats:
            return 1.0 / math.log2(i + 2)  # IDCG = 1/log2(2)=1.0, langsung return
    return 0.0


with app.app_context():
    from models.database import get_db
    from recommendation.knn import knn_recommend, knn_recommend_personalized, get_knn_data_from_db

    db = get_db()
    all_ratings    = [dict(r) for r in db.execute('SELECT user_id, produk_id, score FROM ratings').fetchall()]
    all_produk_ids = [r['id'] for r in db.execute('SELECT id FROM produk WHERE tersedia=1').fetchall()]

    products_data, kategori_ids = get_knn_data_from_db()
    prod_map    = {p['id']: p for p in products_data}
    pid_to_kat  = {p['id']: p['kategori_id'] for p in products_data}

    user_map = {}
    for r in all_ratings:
        uid = r['user_id']
        if uid not in user_map:
            user_map[uid] = []
        user_map[uid].append(r)

    MIN_RATINGS = 3
    user_map = {uid: rts for uid, rts in user_map.items() if len(rts) >= MIN_RATINGS}

    n_users  = len(user_map)
    n_produk = len(all_produk_ids)

    print("=" * 95)
    print(" EVALUASI KNN — Variasi Nilai K (LOOCV, Fixed NDCG)")
    print(f" Total User Eligible : {n_users} (min {MIN_RATINGS} rating) | Total Produk: {n_produk}")
    print(f" Metode              : Leave-One-Out Cross Validation per User")
    print("=" * 95)

    K_values = [3, 5, 10, 20]
    results  = []

    for K in K_values:
        prec_list, ndcg_list, hr_list, time_list = [], [], [], []
        coverage_set = set()

        for uid, all_rts in user_map.items():
            loocv_prec, loocv_ndcg, loocv_hr = [], [], []

            for test_idx in range(len(all_rts)):
                test_item  = all_rts[test_idx]
                train_fold = [r for i, r in enumerate(all_rts) if i != test_idx]

                test_pid  = test_item['produk_id']
                test_kat  = pid_to_kat.get(test_pid)

                # Guard: skip jika kategori tidak dikenali
                if test_kat is None:
                    continue

                relevant_kats = {test_kat}

                train_pids = [r['produk_id'] for r in train_fold]
                pref_kats  = list(set(
                    prod_map[p]['kategori_id']
                    for p in train_pids if p in prod_map
                ))
                exclude = set(train_pids)

                t0 = time.perf_counter()
                if pref_kats:
                    recs_raw = knn_recommend_personalized(
                        products_data, kategori_ids, pref_kats,
                        n_recommendations=K + len(exclude)
                    )
                else:
                    recs_raw = knn_recommend(
                        products_data, kategori_ids,
                        n_recommendations=K + len(exclude)
                    )
                elapsed = (time.perf_counter() - t0) * 1000

                recs = [p for p in recs_raw if p not in exclude][:K]
                coverage_set.update(recs)
                time_list.append(elapsed)

                # 1. Item Hit Rate
                loocv_hr.append(1 if test_pid in recs else 0)

                # 2. Category Precision@K
                recs_kats = [pid_to_kat.get(p) for p in recs]
                hits = sum(1 for kat in recs_kats if kat is not None and kat in relevant_kats)
                loocv_prec.append(hits / K if K > 0 else 0)

                # 3. Category NDCG@K (IDCG=1.0 karena hanya 1 item relevan)
                loocv_ndcg.append(hitung_ndcg(recs_kats, relevant_kats, K))

            if loocv_prec:
                prec_list.append(np.mean(loocv_prec))
                ndcg_list.append(np.mean(loocv_ndcg))
                hr_list.append(np.mean(loocv_hr))

        results.append({
            "K"        : K,
            "precision": np.mean(prec_list) if prec_list else 0,
            "ndcg"     : np.mean(ndcg_list) if ndcg_list else 0,
            "hit_rate" : np.mean(hr_list)   if hr_list   else 0,
            "time_ms"  : np.mean(time_list) if time_list else 0,
            "coverage" : len(coverage_set) / n_produk if n_produk > 0 else 0,
        })

    sep    = "-" * 95
    header = (f"{'K':<6} {'Cat. Precision@K':<18} {'Cat. NDCG@K':<15} "
              f"{'Item Hit Rate@K':<18} {'Avg Time (ms)':<16} {'Coverage':<10}")
    print(f"\n{header}")
    print(sep)
    for r in results:
        print(
            f"{r['K']:<6} "
            f"{r['precision']:<18.4f} "
            f"{r['ndcg']:<15.4f} "
            f"{r['hit_rate']:<18.4f} "
            f"{r['time_ms']:<16.2f} "
            f"{r['coverage']:<10.4f}"
        )
    print("=" * 95)
    print()
    print(" Interpretasi metrik:")
    print("   Cat. Precision@K : proporsi rekomendasi yang kategorinya cocok dengan test item")
    print("   Cat. NDCG@K      : 1.0 jika kategori cocok di posisi 1, turun jika posisinya lebih jauh")
    print("   Item Hit Rate@K  : proporsi kasus di mana produk spesifik berhasil direkomendasikan")
    print("   Coverage         : proporsi katalog yang pernah direkomendasikan")