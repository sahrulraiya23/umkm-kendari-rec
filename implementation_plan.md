# Professional Design Overhaul — UMKM Kendari

Redesign seluruh UI agar lebih profesional, modern, dan premium tanpa mengubah struktur backend/routing Flask.

## Proposed Changes

### Pendekatan Utama
Fokus pengerjaan ada di **CSS** dan **HTML template** — tidak ada perubahan pada Python/Flask backend. Semua endpoint, route, dan logika tetap sama.

---

### Design System — Perubahan Kunci

| Aspek | Sebelum | Sesudah |
|-------|---------|---------|
| **Color Palette** | Flat blue (#1A56DB) | Rich indigo-blue gradient palette dengan warm accent |
| **Typography** | Inter saja | Inter + Plus Jakarta Sans (headings) |
| **Card Style** | Simple border + shadow | Glassmorphism yang lebih refined, hover glow |
| **Navbar** | Flat white bar | Backdrop-blur premium dengan animated indicator |
| **Hero Section** | Text-only gradient | Animated particles/mesh background, floating badge |
| **Product Cards** | Basic hover translateY | Perspective 3D tilt, shimmer effect, gradient overlay |
| **Footer** | Simple gradient | Multi-column footer dengan social links effect |
| **Buttons** | Basic gradient | Animated gradient shift + ripple effect |
| **Forms** | Standard inputs | Floating labels, animated focus states |
| **Animations** | Minimal | Scroll-reveal, stagger, micro-interactions |

---

### Komponen yang Diubah

#### [MODIFY] [style.css](file:///c:/Users/Raiya/umkm-kendari-rec/static/css/style.css)
- Complete overhaul CSS variables (refined color palette, lebih banyak shadows & gradients)
- Tambah animasi: `@keyframes slideUp`, `fadeIn`, `shimmer`, `gradientShift`, `float`
- Navbar: sticky glassmorphism + animated underline indicator pada nav link
- Hero: Animated mesh gradient background + badge pulse
- Product cards: 3D perspective hover, gradient overlay pada image, shimmer loading
- Buttons: gradient animation, ripple effect
- Forms: floating label style, glow focus
- Tables: striped + hover highlight yang lebih halus
- Footer: multi-section, animated link underline
- Scroll-triggered reveal animations
- Improved responsive breakpoints

#### [MODIFY] [base.html](file:///c:/Users/Raiya/umkm-kendari-rec/templates/base.html)
- Tambah Google Font `Plus Jakarta Sans`
- Navbar redesign: hamburger menu mobile, animated brand logo
- Footer: multi-column layout, lebih informative
- Tambah animated page loader

#### [MODIFY] [index.html](file:///c:/Users/Raiya/umkm-kendari-rec/templates/index.html)
- Hero: animated mesh gradient, floating elements, better CTA layout
- Kategori: icon cards dengan colored accent per kategori
- Product cards: konsisten pakai class-based styling (remove inline styles)
- Section dividers yang lebih elegan

#### [MODIFY] [login.html](file:///c:/Users/Raiya/umkm-kendari-rec/templates/auth/login.html)
- Split layout: ilustrasi/branding panel + form panel
- Animated form fields, password toggle

#### [MODIFY] [register.html](file:///c:/Users/Raiya/umkm-kendari-rec/templates/auth/register.html)
- Multi-step visual indicator
- Animated form elements

#### [MODIFY] [detail.html](file:///c:/Users/Raiya/umkm-kendari-rec/templates/produk/detail.html)
- Image gallery dengan zoom hover
- Better info layout, review section cards

#### [MODIFY] [list.html](file:///c:/Users/Raiya/umkm-kendari-rec/templates/produk/list.html)
- Better filter UI, animated grid transitions

#### [MODIFY] [profil.html](file:///c:/Users/Raiya/umkm-kendari-rec/templates/user/profil.html)
- Avatar lebih premium, stats dengan mini charts

#### [MODIFY] [wishlist.html](file:///c:/Users/Raiya/umkm-kendari-rec/templates/user/wishlist.html)
- Empty state illustration, better card layout  

#### [MODIFY] [chatbot.html](file:///c:/Users/Raiya/umkm-kendari-rec/templates/chatbot.html)
- More polished bubble design, gradient header

#### [MODIFY] [tentang.html](file:///c:/Users/Raiya/umkm-kendari-rec/templates/tentang.html)
- Better flow diagram, tech cards yang lebih menarik

#### [MODIFY] [admin/dashboard.html](file:///c:/Users/Raiya/umkm-kendari-rec/templates/admin/dashboard.html)
- Better stat cards + improved chart styling

#### [MODIFY] [main.js](file:///c:/Users/Raiya/umkm-kendari-rec/static/js/main.js)
- Tambah scroll-reveal animations
- Smooth page transitions
- Navbar scroll behavior 
- Ripple effect handler
- Counter animation

---

## Verification Plan

### Manual Verification
- Jalankan Flask app: `python app.py`
- Buka di browser → cek setiap halaman secara visual
- Verifikasi responsive di mobile width
- Pastikan semua fungsi (login, register, rating, wishlist, chatbot) tetap bekerja
