# Plan Peningkatan Akurasi Sistem Rekomendasi UMKM Kendari

**Status Saat Ini:**
- NCF: Hit Rate 0.15-0.21 (cold-start), 0.82-1.00 (3+ ratings) ✓ Sudah bagus
- KNN: Hit Rate 0.55-0.80 (konsisten) - Perlu ditingkatkan
- Switching Point: 3 rating (sudah optimal)
- Data Sparsity: Kemungkinan masalah utama

---

## TIER 1: QUICK WINS (Implementasi 1-2 hari)

### 1.1 Tambah Implicit Feedback (Click & View)
**Problem:** Hanya menggunakan explicit ratings (1-5), data sangat sparse  
**Solusi:** Catat user interaction: page view, product click, wishlist add

**Implementasi:**
```
Model yang dibutuhkan:
- user_interactions (user_id, produk_id, type, timestamp)
  - type: 'view', 'click', 'wishlist', 'rating'

Scoring:
- View = 0.3 poin
- Click = 0.5 poin  
- Wishlist = 1.0 poin
- Rating 4-5 = 2.0 poin
- Rating 1-2 = -1.0 poin

NCF Training:
- Kombinasi explicit (ratings) + implicit (interactions)
- Berat rating 2x lebih tinggi dari implicit
```

**File yang perlu edit:** [models/database.py](models/database.py) (tambah tabel)

---

### 1.2 Fix NCF Cold-Start (0.15 → 0.40+)
**Problem:** NCF performance sangat jelek untuk 1-2 rating

**Solusi (TETAP EKSKLUSIF ARCHITECTURE):**

**a) Improve KNN untuk 1-2 Rating**
```python
# Jika user < 3 rating, TETAP gunakan KNN (jangan switch ke NCF)
# Tapi TINGKATKAN KNN dengan:
# 1. Enhanced features (seller score, trending, recency)
# 2. Better similarity weighting
# 3. Preference-based filtering

# Expected: KNN 0.55-0.64 → 0.75+
```

**b) Data Augmentation untuk NCF Training**
```python
# Saat user lihat produk kategori X, treat sebagai implicit signal
# Implicit feedback weight untuk TRAINING SAJA:
# - page_view → weight 0.3 (training only)
# - click → weight 0.5 (training only)
# - wishlist → weight 1.0 (training only)
# - rating → weight 2.0 (training only)

# Benefit: NCF matrix lebih dense, faster convergence
# Jangan campur di inference - tetap 3+ rating untuk switch
```

**c) Lower Switching Threshold (Optional)**
```python
# Current: NCF_MIN_RATINGS = 3
# Option: Turun ke 2-3 (pilihan)
# Tapi jangan ke 1 - terlalu berisiko

# Trade-off:
# - 3 ratings: More robust, safer
# - 2 ratings: Faster personalization, tapi noise lebih tinggi
```

**d) Tuning KNN + NCF Hyperparameter**
```python
# KNN: Fix tidak ada (algoritma simple, tuning via features)

# NCF Hyperparameter:
embedding_dim=32  # Lebih kecil untuk sparse data
epochs=120        # Lebih banyak convergence
lr=0.001         # Learning rate lebih tinggi
batch_size=32    # Match dengan data size
dropout=0.15     # Regularisasi moderate
early_stopping=15 # Stop jika val_loss stagnan

# Result: NCF quality lebih baik saat used (>= 3 rating)
```

**File yang perlu edit:** [recommendation/ncf.py](recommendation/ncf.py) dan [recommendation/engine.py](recommendation/engine.py)

---

### 1.3 Tingkatkan KNN Features (0.80 → 0.85+)
**Problem:** KNN hanya pakai kategori + harga + avg_rating

**Tambahan Features:**
```python
1. Seller reputation score
   - Rating seller rata-rata
   - Jumlah total rating seller
   - Response time seller
   
2. Product recency weight
   - Produk baru di-boost (boost factor 1.2)
   - Product age normalization
   
3. Trending score
   - Jumlah rating dalam 7 hari terakhir
   - Click rate dalam 7 hari
   
4. Category popularity
   - Boost kategori yang trending
   
5. Similarity ke wishlist user
   - Jika produk mirip dengan wishlist → boost
```

**Implementation Pseudocode:**
```python
def knn_recommend_enhanced(products_data, user_id=None):
    # Feature matrix: kategori + harga + rating + seller_score + recency + trending + wishlist_sim
    # Bobot feature: 0.3 kategori, 0.15 harga, 0.15 rating, 0.1 seller, 0.1 recency, 0.1 trending, 0.1 wishlist
    pass
```

**File yang perlu edit:** [recommendation/knn.py](recommendation/knn.py)

---

## TIER 2: MEDIUM EFFORT (Implementasi 3-5 hari)

### 2.1 Matrix Factorization + NCF Hybrid
**Problem:** NCF terlalu bergantung pada embeddings

**Solusi:** Gabung NCF dengan SVD/NMF untuk sparse matrix
```python
class HybridNCF:
    1. Jalankan SVD pada user-produk matrix → latent factors
    2. Gunakan latent factors sebagai additional features ke NCF
    3. Kombinasi: NCF output 0.7 + SVD prediction 0.3
    
Benefit: Lebih robust untuk sparse data
```

**File baru:** `recommendation/hybrid_ncf.py`

---

### 2.2 Clustering-based Cold Start
**Problem:** User baru tanpa preference sulit di-handle

**Solusi:** User Clustering
```python
1. Cluster users based on preference + behavior
   - Menggunakan K-means pada preference vector + interaction history
   - K = 5-10 clusters (test optimal)
   
2. Cold start user → assign ke cluster terdekat
   
3. Rekomendasikan top items dari cluster
   - Lebih baik dari purely random/popular

Accuracy improvement: 0.15 → 0.40 (estimated)
```

**File baru:** `recommendation/clustering.py`

---

### 2.3 A/B Testing Framework
**Purpose:** Validate improvement sebelum deploy

**Implementation:**
```python
# models/experiment.py
class Experiment:
    - experiment_id, name, start_date
    - control_method (KNN/NCF/current)
    - test_method (new hybrid/ensemble)
    - user_buckets (50% control, 50% test)
    - track: click_rate, conversion_rate, revenue
    
# routes/experiment.py
- GET /experiments - list running experiments
- POST /experiments - create new experiment
- GET /experiments/{id}/results - view results with significance test
```

---

## TIER 3: ADVANCED (Implementasi 1-2 minggu)

### 3.1 Content-Based Feature Extraction
**Current:** Hanya category, price, rating  
**Improved:** Extract dari deskripsi produk

```python
# recommendation/content_extraction.py
1. TF-IDF dari deskripsi produk
   - Top 50 terms per category
   - Normalize dengan category popularity
   
2. Embedding dari deskripsi (pre-trained)
   - Gunakan sentence-transformers: 'paraphrase-MiniLM-L6-v2'
   - Create semantic similarity matrix
   
3. Visual features (jika ada image)
   - Color histogram
   - Object detection (mobilenet)
   
Feature weight: 0.3 untuk semantic similarity
```

---

### 3.2 Temporal Dynamics
**Problem:** Preferensi user berubah seiring waktu

**Solusi:** Time-Aware Recommendation
```python
1. Decay factor untuk old ratings
   - Rating 1 bulan lalu: weight 0.8
   - Rating 3 bulan lalu: weight 0.6
   - Rating 6+ bulan lalu: weight 0.3
   
2. Session-based recommendation
   - Track user session browsing
   - Recommend produk mirip dengan recent clicks
   
3. Seasonal trends
   - Boost produk seasonal (cek dari trend score)
```

---

### 3.3 Deep Learning Model (Advanced)
**Jika masih perlu peningkatan:** Wide & Deep Networks
```python
# recommendation/wide_deep.py
- Wide: memorize popular patterns (KNN-like)
- Deep: learn complex interactions (NCF-like)
- Output: blended prediction

Benefit:
- Lebih fleksibel dari pure NCF
- Handle sparse + dense data lebih baik
- SOTA performance (estimated 0.90+)
```

---

## TIER 4: MEASUREMENT & MONITORING

### 4.1 Metrik yang Harus Ditrack
```
1. Offline Metrics:
   ✓ Hit Rate@K (current)
   ✓ NDCG@K (ranking quality)
   ✓ Precision/Recall@K
   - Coverage (% produk yang pernah direkomendasi)
   - Diversity (% variety dalam rekomendasi)
   
2. Online Metrics:
   - Click-Through Rate (CTR)
   - Conversion Rate
   - Average Order Value (AOV)
   - User engagement (session length)
   - Recommendation freshness

3. Business Metrics:
   - Revenue per user
   - Customer Lifetime Value
   - Repeat purchase rate
```

### 4.2 Monitoring Dashboard Update
```
File: templates/admin/evaluasi.html
Update untuk show:
- Real-time performance by method (KNN/NCF/Hybrid)
- Performance by user segment (cold-start/warm/active)
- Feature importance (dari model explainability)
- Anomaly detection (sudden drop in accuracy)
```

---

## IMPLEMENTATION ROADMAP

### Week 1 (Priority HIGH):
- [ ] 1.1: Add implicit feedback model
- [ ] 1.2: Fix NCF cold-start with hybrid ensemble
- [ ] 1.3: Enhance KNN features

### Week 2 (Priority MEDIUM):
- [ ] 2.1: Hybrid NCF implementation
- [ ] 2.2: Clustering for cold start
- [ ] 2.3: A/B testing framework

### Week 3+ (Priority LOW):
- [ ] 3.1: Content-based extraction
- [ ] 3.2: Temporal dynamics
- [ ] 3.3: Wide & Deep model

---

## Expected Accuracy Improvement

| Scenario | Current | After TIER 1 | After TIER 2 | After TIER 3 |
|----------|---------|-------------|-------------|-------------|
| Cold-Start (0-2 rating) | 0.55 (KNN) | 0.75+ (Enhanced KNN) | 0.80+ (Cluster KNN) | 0.85+ (Content-based) |
| Warm (3-5 rating) | 0.82 (NCF) | 0.88+ (Better NCF) | 0.92+ (Hybrid NCF) | 0.95+ (Wide & Deep) |
| Active (5+ rating) | 1.00 (NCF) | 1.00 (NCF) | 1.00 (NCF) | 1.00 (NCF) |
| **Overall Avg** | **0.79** | **0.84** | **0.89** | **0.93** |

**Catatan:** TIER 1 tetap eksklusif (KNN XOR NCF), tidak ada blending

---

## Quick Decision Matrix

**Pilih TIER 1 jika:**
- Butuh improvement cepat (1-2 hari)
- Budget/resources terbatas
- Target: improve cold-start

**Pilih TIER 1 + 2 jika:**
- Timeframe 2 minggu
- Ingin robust solution
- Target: 0.84+ accuracy

**Pilih TIER 1 + 2 + 3 jika:**
- Timeline 1 bulan+
- Ingin production-grade system
- Target: 0.90+ accuracy (SOTA)

---

## Notes
- Semua implementasi bisa di-track dengan git commits
- Ada fallback ke current system di setiap step
- Recommended: test lokal dulu sebelum deploy
