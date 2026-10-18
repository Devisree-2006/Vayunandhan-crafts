/**
 * Vayunandhan Crafts — Main JavaScript
 * Vanilla JS only. No framework dependencies.
 */

'use strict';

/* ── Mobile Navigation ──────────────────────────────────────────────────────── */
function initMobileNav() {
  const hamburger = document.getElementById('hamburger');
  const overlay   = document.getElementById('mobileNavOverlay');
  const drawer    = document.getElementById('mobileNav');
  const closeBtn  = document.getElementById('mobileNavClose');

  if (!hamburger) return;

  function openNav() {
    overlay.classList.add('open');
    drawer.classList.add('open');
    document.body.style.overflow = 'hidden';
  }
  function closeNav() {
    overlay.classList.remove('open');
    drawer.classList.remove('open');
    document.body.style.overflow = '';
  }

  hamburger.addEventListener('click', openNav);
  closeBtn.addEventListener('click', closeNav);
  overlay.addEventListener('click', closeNav);
  document.addEventListener('keydown', e => { if (e.key === 'Escape') closeNav(); });
}

/* ── Toast Notifications ────────────────────────────────────────────────────── */
function showToast(message, type = 'success', duration = 3500) {
  let container = document.getElementById('toastContainer');
  if (!container) {
    container = document.createElement('div');
    container.id = 'toastContainer';
    container.setAttribute('aria-live', 'polite');
    container.style.cssText = `
      position:fixed; bottom:1.5rem; left:50%; transform:translateX(-50%);
      z-index:9999; display:flex; flex-direction:column; gap:.5rem; align-items:center;
      pointer-events:none;
    `;
    document.body.appendChild(container);
  }

  const icons = { success: '✅', error: '❌', warning: '⚠️', info: 'ℹ️' };
  const colors = {
    success: '#2e7d32', error: '#c62828', warning: '#e65100', info: '#1565c0'
  };

  const toast = document.createElement('div');
  toast.style.cssText = `
    background:#fff; color:${colors[type] || colors.info};
    padding:.75rem 1.25rem; border-radius:999px;
    box-shadow:0 4px 20px rgba(0,0,0,.15);
    font-size:.9rem; font-weight:700;
    display:flex; align-items:center; gap:.5rem;
    pointer-events:auto; opacity:0;
    transition:opacity .3s ease, transform .3s ease;
    transform:translateY(8px);
    border-left:4px solid ${colors[type] || colors.info};
  `;
  toast.textContent = (icons[type] || '') + ' ' + message;
  container.appendChild(toast);

  requestAnimationFrame(() => {
    toast.style.opacity = '1';
    toast.style.transform = 'translateY(0)';
  });

  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateY(8px)';
    setTimeout(() => toast.remove(), 320);
  }, duration);
}

/* ── Cart Quantity Controls ─────────────────────────────────────────────────── */
function initCartControls() {
  document.addEventListener('click', async function(e) {
    const btn = e.target.closest('[data-cart-action]');
    if (!btn) return;

    const action     = btn.dataset.cartAction;  // 'increase' | 'decrease' | 'remove'
    const itemId     = btn.dataset.itemId;
    const csrfToken  = getCsrf();

    if (!itemId) return;

    btn.disabled = true;

    try {
      const resp = await fetch('/orders/cart/update/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': csrfToken,
          'X-Requested-With': 'XMLHttpRequest',
        },
        body: JSON.stringify({ item_id: itemId, action }),
      });

      const data = await resp.json();

      if (!resp.ok || data.error) {
        showToast(data.error || 'Something went wrong', 'error');
      } else {
        // Reload the cart section or full page
        if (data.redirect) {
          window.location.href = data.redirect;
        } else {
          refreshCart(data);
        }
      }
    } catch {
      showToast('Network error. Please try again.', 'error');
    } finally {
      btn.disabled = false;
    }
  });
}

function refreshCart(data) {
  // Update cart count badge in navbar
  const badge = document.getElementById('cartCountBadge');
  if (badge) badge.textContent = data.cart_count || 0;

  // If a cart item row exists, update or remove it
  if (data.item_id) {
    const row = document.querySelector(`[data-cart-item="${data.item_id}"]`);
    if (row) {
      if (data.quantity <= 0) {
        row.remove();
      } else {
        const qtyEl = row.querySelector('.qty-value');
        const subEl = row.querySelector('.cart-item-subtotal');
        if (qtyEl) qtyEl.textContent = data.quantity;
        if (subEl) subEl.textContent = '₹' + formatMoney(data.subtotal);
      }
    }
  }

  // Update totals
  if (data.summary) {
    const s = data.summary;
    setText('summarySubtotal',   '₹' + formatMoney(s.subtotal));
    setText('summaryDelivery',   '₹' + formatMoney(s.delivery));
    setText('summaryDiscount',  '-₹' + formatMoney(s.discount));
    setText('summaryTotal',      '₹' + formatMoney(s.total));
  }

  if (data.cart_count === 0) {
    const cartBody = document.getElementById('cartBody');
    if (cartBody) {
      cartBody.innerHTML = `
        <div class="empty-state">
          <div class="empty-state__icon">🛍️</div>
          <h3 class="empty-state__title">Your cart is empty</h3>
          <p class="empty-state__text">Add some handmade magic to your cart!</p>
          <a href="/shop/" class="btn btn-primary">Browse Products</a>
        </div>`;
    }
  }
}

/* ── Add-to-Cart (Product pages) ────────────────────────────────────────────── */
function initAddToCart() {
  const forms = document.querySelectorAll('.add-to-cart-form');
  forms.forEach(form => {
    form.addEventListener('submit', async function(e) {
      e.preventDefault();
      const btn  = form.querySelector('[type="submit"]');
      const orig = btn.textContent;
      btn.disabled = true;
      btn.textContent = 'Adding…';

      try {
        const resp = await fetch(form.action, {
          method: 'POST',
          body:   new FormData(form),
          headers: { 'X-Requested-With': 'XMLHttpRequest' },
        });
        const data = await resp.json();

        if (!resp.ok || data.error) {
          showToast(data.error || 'Could not add to cart', 'error');
        } else {
          showToast(data.message || 'Added to cart!', 'success');
          const badge = document.getElementById('cartCountBadge');
          if (badge) badge.textContent = data.cart_count;
        }
      } catch {
        showToast('Network error. Please try again.', 'error');
      } finally {
        btn.disabled = false;
        btn.textContent = orig;
      }
    });
  });
}

/* ── Product Gallery (Detail page) ─────────────────────────────────────────── */
function initProductGallery() {
  const mainImg   = document.getElementById('galleryMain');
  const thumbs    = document.querySelectorAll('.product-gallery__thumb');
  if (!mainImg || !thumbs.length) return;

  thumbs.forEach(thumb => {
    thumb.addEventListener('click', function() {
      mainImg.src = this.dataset.full || this.querySelector('img').src;
      mainImg.alt = this.querySelector('img').alt;
      thumbs.forEach(t => t.classList.remove('active'));
      this.classList.add('active');
    });
  });
}

/* ── Django Messages → Toasts ───────────────────────────────────────────────── */
function initDjangoMessages() {
  document.querySelectorAll('[data-django-message]').forEach(el => {
    const type = el.dataset.djangoMessage;
    const text = el.textContent.trim();
    if (text) showToast(text, type === 'error' ? 'error' : type === 'warning' ? 'warning' : 'success');
    el.remove();
  });
}

/* ── Countdown banner (offers) ──────────────────────────────────────────────── */
function initCountdown() {
  const el = document.getElementById('offerCountdown');
  if (!el) return;
  const target = new Date(el.dataset.until);

  function tick() {
    const diff = target - new Date();
    if (diff <= 0) { el.textContent = 'Offer ended'; return; }
    const h = Math.floor(diff / 3600000);
    const m = Math.floor((diff % 3600000) / 60000);
    const s = Math.floor((diff % 60000) / 1000);
    el.textContent = `${pad(h)}h ${pad(m)}m ${pad(s)}s`;
  }
  tick();
  setInterval(tick, 1000);
}
function pad(n) { return String(n).padStart(2, '0'); }

/* ── Razorpay Checkout ──────────────────────────────────────────────────────── */
function initRazorpay() {
  const btn = document.getElementById('razorpayPayBtn');
  if (!btn) return;

  btn.addEventListener('click', async function() {
    btn.disabled = true;
    btn.textContent = 'Please wait…';

    const csrfToken = getCsrf();

    try {
      const resp = await fetch('/payments/razorpay/initiate/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': csrfToken,
          'X-Requested-With': 'XMLHttpRequest',
        },
        body: JSON.stringify({ order_ref: btn.dataset.orderRef }),
      });
      const data = await resp.json();

      if (!resp.ok || data.error) {
        showToast(data.error || 'Could not initiate payment', 'error');
        btn.disabled = false;
        btn.textContent = 'Pay Now';
        return;
      }

      const options = {
        key:          data.key_id,
        amount:       data.amount,
        currency:     data.currency,
        name:         data.store_name,
        description:  'Order ' + data.order_ref,
        order_id:     data.razorpay_order_id,
        prefill: {
          name:    data.customer_name,
          email:   data.customer_email,
          contact: data.customer_phone,
        },
        theme: { color: '#e8647a' },
        modal: {
          ondismiss: function() {
            btn.disabled = false;
            btn.textContent = 'Pay Now';
            showToast('Payment cancelled. You can try again.', 'warning');
          },
        },
        handler: function(response) {
          // Submit verified fields to backend
          const form = document.getElementById('razorpayCallbackForm');
          if (form) {
            form.querySelector('[name="razorpay_payment_id"]').value = response.razorpay_payment_id;
            form.querySelector('[name="razorpay_order_id"]').value   = response.razorpay_order_id;
            form.querySelector('[name="razorpay_signature"]').value  = response.razorpay_signature;
            form.submit();
          }
        },
      };

      const rzp = new Razorpay(options);
      rzp.open();

    } catch {
      showToast('Network error. Please try again.', 'error');
      btn.disabled = false;
      btn.textContent = 'Pay Now';
    }
  });
}

/* ── UPI Screenshot preview ─────────────────────────────────────────────────── */
function initUpiUpload() {
  const input   = document.getElementById('upiScreenshot');
  const preview = document.getElementById('upiScreenshotPreview');
  if (!input || !preview) return;

  input.addEventListener('change', function() {
    const file = this.files[0];
    if (!file) return;

    const allowed = ['image/jpeg', 'image/png', 'image/webp'];
    if (!allowed.includes(file.type)) {
      showToast('Only JPG, PNG, or WebP images are allowed', 'error');
      this.value = '';
      return;
    }
    if (file.size > 5 * 1024 * 1024) {
      showToast('Image must be under 5 MB', 'error');
      this.value = '';
      return;
    }

    const reader = new FileReader();
    reader.onload = e => {
      preview.src = e.target.result;
      preview.parentElement.classList.remove('hidden');
    };
    reader.readAsDataURL(file);
  });
}

/* ── Search Suggestions (minimal debounce) ──────────────────────────────────── */
function initSearch() {
  const input = document.getElementById('searchInput');
  if (!input) return;

  let timer;
  input.addEventListener('input', function() {
    clearTimeout(timer);
    timer = setTimeout(() => {
      if (this.value.length >= 2) {
        this.form.submit();
      }
    }, 600);
  });
}

/* ── Helpers ────────────────────────────────────────────────────────────────── */
function getCsrf() {
  const cookie = document.cookie.split(';').find(c => c.trim().startsWith('csrftoken='));
  if (cookie) return cookie.split('=')[1].trim();
  const meta = document.querySelector('meta[name="csrf-token"]');
  return meta ? meta.content : '';
}

function setText(id, text) {
  const el = document.getElementById(id);
  if (el) el.textContent = text;
}

function formatMoney(n) {
  return parseFloat(n).toFixed(2).replace(/\B(?=(\d{3})+(?!\d))/g, ',');
}

/* ── Init ────────────────────────────────────────────────────────────────────── */
document.addEventListener('DOMContentLoaded', function() {
  initMobileNav();
  initAddToCart();
  initCartControls();
  initProductGallery();
  initDjangoMessages();
  initCountdown();
  initRazorpay();
  initUpiUpload();
  initSearch();
});
