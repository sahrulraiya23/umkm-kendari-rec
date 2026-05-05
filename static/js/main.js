// ====================================
// UMKM Kendari — Premium JavaScript
// ====================================

document.addEventListener('DOMContentLoaded', function () {

    // --- Page loader ---
    const loader = document.getElementById('pageLoader');
    if (loader) {
        setTimeout(function () {
            loader.classList.add('hide');
            setTimeout(function () { loader.remove(); }, 500);
        }, 300);
    }

    // --- Navbar scroll behavior ---
    const navbar = document.getElementById('mainNav');
    if (navbar) {
        let lastScroll = 0;
        window.addEventListener('scroll', function () {
            const current = window.scrollY;
            if (current > 20) {
                navbar.classList.add('scrolled');
            } else {
                navbar.classList.remove('scrolled');
            }
            lastScroll = current;
        }, { passive: true });
    }

    // --- Scroll-reveal animations ---
    const observerOptions = {
        threshold: 0.08,
        rootMargin: '0px 0px -40px 0px'
    };

    const revealObserver = new IntersectionObserver(function (entries) {
        entries.forEach(function (entry, index) {
            if (entry.isIntersecting) {
                // Stagger delay based on sibling index
                const siblings = entry.target.parentElement ?
                    Array.from(entry.target.parentElement.children).filter(c => c.classList.contains('reveal')) : [];
                const sibIndex = siblings.indexOf(entry.target);
                const delay = Math.min(sibIndex * 80, 400);

                setTimeout(function () {
                    entry.target.classList.add('revealed');
                }, delay);
                revealObserver.unobserve(entry.target);
            }
        });
    }, observerOptions);

    // Observe product cards & elements with .reveal class
    document.querySelectorAll('.product-card, .stat-card, .glass-card, .review-card, .kategori-card').forEach(function (el) {
        el.classList.add('reveal');
        revealObserver.observe(el);
    });

    document.querySelectorAll('.reveal').forEach(function (el) {
        if (!el.classList.contains('revealed')) {
            revealObserver.observe(el);
        }
    });

    // --- Close modal on backdrop click ---
    document.querySelectorAll('.modal-backdrop').forEach(function (modal) {
        modal.addEventListener('click', function (e) {
            if (e.target === modal) {
                modal.classList.remove('active');
            }
        });
    });

    // --- Format harga input ---
    const hargaInput = document.getElementById('harga');
    if (hargaInput) {
        hargaInput.addEventListener('input', function () {
            if (this.value < 0) this.value = 0;
        });
    }

    // --- Star rating hover effect ---
    const starLabels = document.querySelectorAll('.star-rating label');
    starLabels.forEach(function (label) {
        label.addEventListener('mouseenter', function () {
            this.style.transform = 'scale(1.25)';
        });
        label.addEventListener('mouseleave', function () {
            this.style.transform = 'scale(1)';
        });
    });

    // --- Smooth scroll for anchor links ---
    document.querySelectorAll('a[href^="#"]').forEach(function (anchor) {
        anchor.addEventListener('click', function (e) {
            const href = this.getAttribute('href');
            if (href === '#') return;
            e.preventDefault();
            var target = document.querySelector(href);
            if (target) {
                target.scrollIntoView({ behavior: 'smooth', block: 'start' });
            }
        });
    });

    // --- Counter animation for stat numbers ---
    document.querySelectorAll('.stat-number').forEach(function (el) {
        const text = el.textContent.trim();
        const num = parseFloat(text);
        if (!isNaN(num) && num > 0 && num < 100000) {
            const isFloat = text.includes('.');
            const target = num;
            const duration = 1200;
            const start = performance.now();

            const counterObserver = new IntersectionObserver(function (entries) {
                entries.forEach(function (entry) {
                    if (entry.isIntersecting) {
                        function animate(now) {
                            const elapsed = now - start;
                            const progress = Math.min(elapsed / duration, 1);
                            // Ease out cubic
                            const eased = 1 - Math.pow(1 - progress, 3);
                            const current = target * eased;

                            if (isFloat) {
                                el.textContent = current.toFixed(1);
                            } else {
                                el.textContent = Math.floor(current);
                            }

                            if (progress < 1) {
                                requestAnimationFrame(animate);
                            } else {
                                el.textContent = text; // restore original
                            }
                        }
                        el.textContent = isFloat ? '0.0' : '0';
                        requestAnimationFrame(animate);
                        counterObserver.unobserve(entry.target);
                    }
                });
            }, { threshold: 0.5 });

            counterObserver.observe(el);
        }
    });

    // --- Button ripple effect ---
    document.querySelectorAll('.btn-primary, .btn-success, .btn-danger').forEach(function (btn) {
        btn.addEventListener('click', function (e) {
            const rect = this.getBoundingClientRect();
            const ripple = document.createElement('span');
            const size = Math.max(rect.width, rect.height);
            ripple.style.cssText = `
                position: absolute;
                border-radius: 50%;
                background: rgba(255,255,255,0.3);
                width: ${size}px;
                height: ${size}px;
                left: ${e.clientX - rect.left - size / 2}px;
                top: ${e.clientY - rect.top - size / 2}px;
                transform: scale(0);
                animation: ripple-anim 0.6s ease-out;
                pointer-events: none;
            `;
            this.style.position = 'relative';
            this.style.overflow = 'hidden';
            this.appendChild(ripple);
            setTimeout(() => ripple.remove(), 600);
        });
    });

    // Inject ripple animation
    if (!document.getElementById('ripple-style')) {
        const style = document.createElement('style');
        style.id = 'ripple-style';
        style.textContent = `
            @keyframes ripple-anim {
                to { transform: scale(4); opacity: 0; }
            }
        `;
        document.head.appendChild(style);
    }
});
