# -*- coding: utf-8 -*-
"""
EVALUASI NCF — Fixed v3
Fix:
  - User dengan train_fold kosong (hanya 1 rating) → skip evaluasi NCF,
    masuk segmen tapi HR/NDCG/MAE diisi 0 eksplisit (bukan crash/unknown)
  - all_produk_ids untuk ncf_recommend diganti dengan produk yang ADA
    di model (produk_to_idx), bukan semua produk DB — supaya valid_unrated
    tidak kosong untuk user dengan banyak rating
  - Fallback MAE pakai rata-rata skor training user, bukan hardcode 3.0
"""
import sys, os, time, json
sys.path.insert(0, os.path.dirname(__file__))
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'

from app import create_app
app = create_app()

with app.app_context():
    from models.database import get_db
    from recommendation.ncf import train_ncf_model, ncf_recommend
    from recommendation.evaluation import ndcg_at_k, _get_ncf_predictions
    import numpy as np

    db = get_db()
    all_ratings    = [dict(r) for r in db.execute(
        'SELECT user_id, produk_id, score FROM ratings').fetchall()]
    all_produk_ids = [r['id'] for r in db.execute(
        'SELECT id FROM produk WHERE tersedia=1').fetchall()]

    # --- Grouping & LOO split ---
    user_map = {}
    for r in all_ratings:
        uid = r['user_id']
        if uid not in user_map:
            user_map[uid] = []
        user_map[uid].append(r)

    test_set        = {}
    train_ratings   = []
    user_train_pids = {}

    for uid, rts in user_map.items():
        sorted_r             = sorted(rts, key=lambda x: x['score'], reverse=True)
        test_set[uid]        = sorted_r[0]
        train_fold           = sorted_r[1:]
        train_ratings.extend(train_fold)
        user_train_pids[uid] = [r['produk_id'] for r in train_fold]

    n_users = len(user_map)

    segments_def = {
        "1-4 Rating" : [uid for uid, rts in user_map.items() if 1  <= len(rts) <= 4],
        "5-10 Rating": [uid for uid, rts in user_map.items() if 5  <= len(rts) <= 10],
        ">10 Rating" : [uid for uid, rts in user_map.items() if len(rts) > 10],
    }

    print("=" * 70)
    print("  EVALUASI NCF — Segmentasi Jumlah Interaksi (LOO, Fixed v3)")
    print(f"  Total User  : {n_users} | Total Rating: {len(all_ratings)}")
    print(f"  Training    : {len(train_ratings)} ratings")
    print("=" * 70)
    for seg, uids in segments_def.items():
        n_empty = sum(1 for uid in uids if len(user_train_pids[uid]) == 0)
        print(f"  {seg:<15}: {len(uids)} user ({n_empty} tanpa data training → di-skip NCF)")

    # --- Training NCF ---
    # Hanya latih dengan user yang punya minimal 1 training item
    effective_train = [r for r in train_ratings]  # sudah benar dari LOO
    print(f"\nMelatih NCF dengan {len(effective_train)} ratings...")
    result = train_ncf_model(effective_train, epochs=100)
    print(f"{'OK' if result['success'] else 'GAGAL'}: {result['message']}\n")
    if not result['success']:
        exit()

    # Load mappings
    ncf_mappings_path = os.path.join(
        os.path.dirname(__file__), 'recommendation', 'ncf_mappings.json')
    with open(ncf_mappings_path, 'r') as f:
        mappings = json.load(f)

    # FIX: Gunakan HANYA produk yang dikenal model sebagai kandidat rekomendasi
    # Produk di luar model tidak bisa diprediksi → tidak ada gunanya dimasukkan
    model_produk_ids = [int(pid) for pid in mappings['produk_to_idx'].keys()]

    print(f"Users in model   : {len(mappings['user_to_idx'])}")
    print(f"Products in model: {len(mappings['produk_to_idx'])} / {len(all_produk_ids)} total DB")
    for seg_label, seg_uids in segments_def.items():
        unknown = [uid for uid in seg_uids if str(uid) not in mappings['user_to_idx']]
        tag = f"{len(unknown)} UNKNOWN (akan di-skip)" if unknown else "semua OK"
        print(f"  {seg_label:<15}: {tag}")
    print()

    K_ncf   = 10
    results = []

    for label, uids in segments_def.items():
        if not uids:
            results.append({"label": label, "count": 0,
                            "hr": 0.0, "ndcg": 0.0,
                            "mae": 0.0, "time_ms": 0.0})
            continue

        hr_list, ndcg_list, mae_list, time_list = [], [], [], []

        for uid in uids:
            target    = test_set[uid]
            tgt_pid   = target['produk_id']
            tgt_score = target['score']
            train_pids = user_train_pids[uid]

            # Skip: user tidak dikenal model (train_fold kosong saat training)
            if str(uid) not in mappings['user_to_idx']:
                hr_list.append(0)
                ndcg_list.append(0.0)
                # MAE fallback: pakai mean score user sendiri atau global mean
                fallback = np.mean([r['score'] for r in user_map[uid]]) \
                           if len(user_map[uid]) > 1 else 3.0
                mae_list.append(abs(tgt_score - fallback))
                time_list.append(0.0)
                continue

            # Skip: test item tidak dikenal model → tidak bisa dievaluasi
            if str(tgt_pid) not in mappings['produk_to_idx']:
                hr_list.append(0)
                ndcg_list.append(0.0)
                mae_list.append(abs(tgt_score - 3.0))
                time_list.append(0.0)
                continue

            rel_scores = {tgt_pid: tgt_score}

            t0   = time.perf_counter()
            recs = ncf_recommend(
                uid,
                model_produk_ids,   # FIX: hanya produk yang ada di model
                train_pids,
                n_recommendations=K_ncf
            )
            elapsed = (time.perf_counter() - t0) * 1000

            hr_list.append(1 if tgt_pid in recs else 0)
            ndcg_list.append(ndcg_at_k(recs, rel_scores, k=K_ncf))
            time_list.append(elapsed)

            # MAE: prediksi model untuk test item
            try:
                pred_dict = _get_ncf_predictions(uid, [tgt_pid])
                if tgt_pid in pred_dict:
                    mae_list.append(abs(tgt_score - pred_dict[tgt_pid]))
                else:
                    mae_list.append(abs(tgt_score - 3.0))
            except Exception:
                mae_list.append(abs(tgt_score - 3.0))

        results.append({
            "label"  : label,
            "count"  : len(uids),
            "hr"     : np.mean(hr_list)   if hr_list   else 0.0,
            "ndcg"   : np.mean(ndcg_list) if ndcg_list else 0.0,
            "mae"    : np.mean(mae_list)  if mae_list  else 0.0,
            "time_ms": np.mean(time_list) if time_list else 0.0,
        })

    # --- Tabel ---
    sep    = "-" * 70
    header = (f"{'Segmen Pengguna':<16} {'n':<5} {'HR@10':<10} "
              f"{'NDCG@10':<12} {'MAE':<10} {'Avg Time (ms)'}")
    print(header)
    print(sep)
    for r in results:
        print(f"{r['label']:<16} {r['count']:<5} {r['hr']:<10.4f} "
              f"{r['ndcg']:<12.4f} {r['mae']:<10.4f} {r['time_ms']:<.2f}")
    print("=" * 70)

    active  = [r for r in results if r['count'] > 0]
    total_n = sum(r['count'] for r in active)
    if total_n > 0:
        w = lambda key: sum(r[key] * r['count'] for r in active) / total_n
        print(f"{'RATA-RATA (weighted)':<16} {total_n:<5} "
              f"{w('hr'):<10.4f} {w('ndcg'):<12.4f} "
              f"{w('mae'):<10.4f} {w('time_ms'):<.2f}")
    print("=" * 70)

    # --- Catatan transparan untuk laporan ---
    print()
    n_unknown = sum(
        1 for seg_uids in segments_def.values()
        for uid in seg_uids
        if str(uid) not in mappings['user_to_idx']
    )
    n_tgt_unknown = sum(
        1 for uid in user_map
        if str(test_set[uid]['produk_id']) not in mappings['produk_to_idx']
    )
    print(f"Catatan evaluasi:")
    print(f"  {n_unknown} user di-skip karena tidak ada data training (hanya 1 rating)")
    print(f"  {n_tgt_unknown} user di-skip karena test item tidak dikenal model")
    print(f"  User yang di-skip tetap dihitung dalam n dan berkontribusi HR=0")