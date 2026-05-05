# -*- coding: utf-8 -*-
import matplotlib.pyplot as plt
import numpy as np

# Data dari hasil evaluasi terakhir
labels = ['1-2 Rating', '3 Rating', '4 Rating', '5 Rating', '> 5 Rating']
ncf_hr = [0.1542, 0.8214, 0.8500, 0.8788, 1.0000]
knn_hr = [0.5571, 0.7143, 0.7429, 0.7562, 0.8000]

x = np.arange(len(labels))
width = 0.35

fig, ax = plt.subplots(figsize=(10, 6))

# Membuat Bar Chart
rects1 = ax.bar(x - width/2, ncf_hr, width, label='NCF (Neural)', color='#4e73df')
rects2 = ax.bar(x + width/2, knn_hr, width, label='KNN (Content-Based)', color='#1cc88a')

# Tambahkan Judul dan Label
ax.set_ylabel('Hit Rate @10')
ax.set_title('Perbandingan Performa: NCF vs KNN Berdasarkan Jumlah History')
ax.set_xticks(x)
ax.set_xticklabels(labels)
ax.legend()

# Tambahkan label angka di atas bar
def autolabel(rects):
    for rect in rects:
        height = rect.get_height()
        ax.annotate('{:.2f}'.format(height),
                    xy=(rect.get_x() + rect.get_width() / 2, height),
                    xytext=(0, 3),  # 3 points vertical offset
                    textcoords="offset points",
                    ha='center', va='bottom')

autolabel(rects1)
autolabel(rects2)

# Tambahkan garis "Switching Point"
ax.axvline(x=1.5, color='red', linestyle='--', alpha=0.6)
ax.text(1.6, 0.9, 'Switching Point (Min 3 Rating)', color='red', fontweight='bold')

fig.tight_layout()

# Simpan grafik
plt.savefig('visualisasi_evaluasi.png', dpi=300)
print("✅ Grafik visualisasi berhasil disimpan sebagai 'visualisasi_evaluasi.png'")
