"""
Store customer-facing views.
"""
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.contrib import messages
from django.core.mail import send_mail
from django.conf import settings

from .models import Product, Category, StoreSettings
from .forms import CustomerRegistrationForm, ContactForm


# ── Helpers ──────────────────────────────────────────────────────────────────────

FAQ_ITEMS = [
    {
        'question': 'Are all products 100% handmade?',
        'answer': 'Yes! Every single item in our store is handcrafted by us with love and care. No mass-produced items here.',
    },
    {
        'question': 'How long does delivery take?',
        'answer': 'Standard delivery takes 5–8 business days across India. We ship via trusted courier partners. You\'ll receive a tracking number once your order is dispatched.',
    },
    {
        'question': 'Do you accept custom / personalised orders?',
        'answer': 'Absolutely! We love making personalised gifts. Send us a WhatsApp message or use our Contact form with your requirements and we\'ll get back to you with a quote within 24 hours.',
    },
    {
        'question': 'What payment methods do you accept?',
        'answer': 'We accept all major credit/debit cards, UPI, net banking, and wallets via Razorpay. You can also pay directly via UPI (scan our QR code) and we\'ll verify your payment manually.',
    },
    {
        'question': 'Can I return or exchange a product?',
        'answer': 'We accept returns within 7 days of delivery for damaged or defective items. Personalised / custom items cannot be returned unless they are defective. Please see our Returns Policy for full details.',
    },
    {
        'question': 'Do you offer gift packaging?',
        'answer': 'Yes! All our orders come beautifully packaged. We also offer extra-special gift wrapping with a personalised note card — just mention it in the delivery instructions at checkout.',
    },
    {
        'question': 'My payment went through but I didn\'t get an order confirmation. What do I do?',
        'answer': 'Please check your spam/junk folder first. If you still haven\'t received it after 30 minutes, contact us on WhatsApp with your payment transaction ID and we\'ll sort it out immediately.',
    },
    {
        'question': 'How do I track my order?',
        'answer': 'Visit our Order Tracking page and enter your order reference number and email address. You\'ll be able to see the real-time status of your order.',
    },
]

HAMPER_TIERS = [
    {'label': 'Under ₹299', 'emoji': '💝', 'description': 'Sweet little gifts that don\'t break the bank', 'url': '/shop/?max_price=299&cat=gift-hampers'},
    {'label': '₹299 – ₹499', 'emoji': '🎁', 'description': 'Beautiful hampers for every occasion', 'url': '/shop/?min_price=299&max_price=499&cat=gift-hampers'},
    {'label': '₹499 – ₹799', 'emoji': '🎀', 'description': 'Premium handmade hampers with extra charm', 'url': '/shop/?min_price=499&max_price=799&cat=gift-hampers'},
    {'label': '₹799 & Above', 'emoji': '✨', 'description': 'Luxury gift sets for the most special moments', 'url': '/shop/?min_price=799&cat=gift-hampers'},
]

POLICY_CONTENT = {
    'shipping': {
        'title': 'Shipping & Delivery Policy',
        'content': """
<h2>Shipping & Delivery Policy</h2>
<p><strong>Last updated: 2025</strong></p>

<h3>Delivery Timeframes</h3>
<p>All orders are processed within <strong>1–2 business days</strong> of payment confirmation. Standard delivery across India takes <strong>5–8 business days</strong> after dispatch.</p>

<h3>Delivery Charges</h3>
<p>We offer <strong>free delivery on orders above ₹499</strong>. A flat delivery charge applies to orders below this amount (shown at checkout).</p>

<h3>Shipping Partners</h3>
<p>We ship via trusted courier partners including Delhivery, DTDC, and India Post. A tracking number will be shared via email and WhatsApp once your order is dispatched.</p>

<h3>Remote Areas</h3>
<p>Delivery to remote pin codes may take an additional 2–4 business days. We'll notify you if there are any expected delays.</p>

<h3>Order Tracking</h3>
<p>You can track your order at any time using the <a href="/orders/track/">Order Tracking</a> page with your Order ID and email address.</p>

<h3>Failed Delivery</h3>
<p>If delivery fails due to incorrect address or the recipient being unavailable, the courier will attempt re-delivery. After 2 failed attempts, the package will be returned to us and we'll contact you to arrange re-shipment (additional charges may apply).</p>
""",
    },
    'returns': {
        'title': 'Returns, Refunds & Cancellation Policy',
        'content': """
<h2>Returns, Refunds & Cancellation Policy</h2>
<p><strong>Last updated: 2025</strong></p>

<h3>Return Eligibility</h3>
<p>We accept returns within <strong>7 days of delivery</strong> for items that are:</p>
<ul>
<li>Damaged or defective upon arrival</li>
<li>Significantly different from the product description</li>
<li>Incorrect items shipped</li>
</ul>
<p><strong>Non-returnable items:</strong> Personalised/custom-made items, earrings (for hygiene reasons), and items showing signs of use.</p>

<h3>How to Initiate a Return</h3>
<p>Contact us within 7 days via WhatsApp or email with your Order ID and clear photos of the issue. We'll guide you through the process.</p>

<h3>Refund Process</h3>
<p>Once we receive and inspect the returned item, we'll process your refund within <strong>5–7 business days</strong> to your original payment method.</p>

<h3>Order Cancellation</h3>
<p>Orders can be cancelled within <strong>12 hours of placement</strong> if they haven't been dispatched. Contact us immediately via WhatsApp. Once dispatched, cancellation is not possible.</p>

<h3>Exchange Policy</h3>
<p>We're happy to exchange defective items for the same product (subject to availability). Contact us within 7 days of delivery.</p>
""",
    },
    'privacy': {
        'title': 'Privacy Policy',
        'content': """
<h2>Privacy Policy</h2>
<p><strong>Last updated: 2025</strong></p>

<h3>Information We Collect</h3>
<p>We collect information you provide when placing an order: name, email address, phone number, and delivery address. We also collect payment transaction IDs (but never store your card details — these are handled securely by Razorpay).</p>

<h3>How We Use Your Information</h3>
<ul>
<li>To process and fulfil your order</li>
<li>To send order confirmation and shipping updates via email and WhatsApp</li>
<li>To respond to your enquiries</li>
<li>To improve our products and services</li>
</ul>

<h3>Data Sharing</h3>
<p>We do not sell, trade, or rent your personal information to third parties. We share necessary order details with our courier partners solely for delivery purposes.</p>

<h3>Data Security</h3>
<p>Your data is stored securely. Payment processing is handled by Razorpay, which is PCI-DSS compliant. We never store your card or bank account details.</p>

<h3>Your Rights</h3>
<p>You can request access to, correction of, or deletion of your personal data by contacting us at our store email. We will respond within 30 days.</p>

<h3>Cookies</h3>
<p>We use session cookies to maintain your shopping cart. We do not use third-party tracking cookies.</p>
""",
    },
    'terms': {
        'title': 'Terms & Conditions',
        'content': """
<h2>Terms & Conditions</h2>
<p><strong>Last updated: 2025</strong></p>

<h3>Use of Website</h3>
<p>By accessing and using this website, you agree to these terms. The website and its contents are for personal, non-commercial use only.</p>

<h3>Products & Pricing</h3>
<p>All prices are in Indian Rupees (INR) and are inclusive of applicable taxes. We reserve the right to change prices at any time. Prices at the time of your order placement are binding.</p>

<h3>Orders & Payment</h3>
<p>An order is confirmed only after successful payment verification. For manual UPI payments, orders are confirmed after we verify the transaction. We reserve the right to cancel any order for reasons including pricing errors or stock unavailability.</p>

<h3>Intellectual Property</h3>
<p>All product photos, designs, and content on this website are the property of Vayunandhan Crafts. Reproduction without permission is prohibited.</p>

<h3>Limitation of Liability</h3>
<p>Vayunandhan Crafts shall not be liable for any indirect or consequential losses arising from the use of our products or website.</p>

<h3>Governing Law</h3>
<p>These terms are governed by the laws of India. Any disputes shall be subject to the jurisdiction of courts in India.</p>
""",
    },
}


# ── Views ─────────────────────────────────────────────────────────────────────────

def home(request):
    featured  = Product.objects.filter(status=Product.STATUS_ACTIVE, is_featured=True, stock__gt=0)[:8]
    new_arr   = Product.objects.filter(status=Product.STATUS_ACTIVE, is_new_arrival=True, stock__gt=0)[:8]
    best      = Product.objects.filter(status=Product.STATUS_ACTIVE, is_best_seller=True, stock__gt=0)[:8]
    categories = Category.objects.filter(is_active=True)[:10]

    return render(request, 'store/home.html', {
        'featured_products': featured,
        'new_arrivals': new_arr,
        'best_sellers': best,
        'categories': categories,
        'hamper_tiers': HAMPER_TIERS,
    })


def shop(request):
    qs = Product.objects.filter(status=Product.STATUS_ACTIVE)

    # Category filter via query param
    cat_slug = request.GET.get('cat', '').strip()
    active_category = None
    if cat_slug:
        active_category = Category.objects.filter(slug=cat_slug, is_active=True).first()
        if active_category:
            qs = qs.filter(category=active_category)

    # Price filters
    min_p = request.GET.get('min_price', '').strip()
    max_p = request.GET.get('max_price', '').strip()
    if min_p.isdigit():
        qs = qs.filter(selling_price__gte=min_p)
    if max_p.isdigit():
        qs = qs.filter(selling_price__lte=max_p)

    # Sorting
    sort = request.GET.get('sort', '').strip()
    if sort == 'price_asc':
        qs = qs.order_by('selling_price')
    elif sort == 'price_desc':
        qs = qs.order_by('-selling_price')
    elif sort == 'name':
        qs = qs.order_by('name')
    else:
        qs = qs.order_by('-created_at')

    paginator = Paginator(qs, 16)
    page_obj  = paginator.get_page(request.GET.get('page'))

    return render(request, 'store/shop.html', {
        'page_obj': page_obj,
        'all_categories': Category.objects.filter(is_active=True),
        'active_category': active_category,
        'sort': sort,
    })


def category(request, slug):
    cat = get_object_or_404(Category, slug=slug, is_active=True)
    qs  = Product.objects.filter(status=Product.STATUS_ACTIVE, category=cat)

    sort = request.GET.get('sort', '')
    if sort == 'price_asc':
        qs = qs.order_by('selling_price')
    elif sort == 'price_desc':
        qs = qs.order_by('-selling_price')
    else:
        qs = qs.order_by('-created_at')

    paginator = Paginator(qs, 16)
    page_obj  = paginator.get_page(request.GET.get('page'))

    return render(request, 'store/shop.html', {
        'page_obj': page_obj,
        'all_categories': Category.objects.filter(is_active=True),
        'active_category': cat,
        'sort': sort,
    })


def product_detail(request, slug):
    product = get_object_or_404(Product, slug=slug, status=Product.STATUS_ACTIVE)

    related = Product.objects.filter(
        status=Product.STATUS_ACTIVE,
        category=product.category
    ).exclude(pk=product.pk)[:4]

    return render(request, 'store/product_detail.html', {
        'product': product,
        'related_products': related,
    })


def search(request):
    query = request.GET.get('q', '').strip()
    qs = Product.objects.none()

    if query:
        qs = Product.objects.filter(
            status=Product.STATUS_ACTIVE
        ).filter(
            Q(name__icontains=query) |
            Q(description__icontains=query) |
            Q(category__name__icontains=query) |
            Q(sku__icontains=query)
        ).distinct().order_by('-created_at')

    paginator = Paginator(qs, 16)
    page_obj  = paginator.get_page(request.GET.get('page'))

    return render(request, 'store/search_results.html', {
        'query': query,
        'page_obj': page_obj,
    })


def about(request):
    return render(request, 'store/about.html')


def contact(request):
    form_success = False
    form_errors  = {}
    form_data    = {}

    if request.method == 'POST':
        form = ContactForm(request.POST)
        if form.is_valid():
            cd = form.cleaned_data
            # Send notification email to store
            try:
                store = StoreSettings.get()
                if store.email:
                    send_mail(
                        subject=f'[Contact Form] {cd["subject"]}',
                        message=(
                            f'Name: {cd["name"]}\n'
                            f'Email: {cd["email"]}\n'
                            f'Phone: {cd.get("phone", "")}\n\n'
                            f'Message:\n{cd["message"]}'
                        ),
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=[store.email],
                        fail_silently=True,
                    )
            except Exception:
                pass
            form_success = True
        else:
            form_errors = {f: e[0] for f, e in form.errors.items()}
            form_data   = request.POST.dict()

    return render(request, 'store/contact.html', {
        'form_success': form_success,
        'form_errors': form_errors,
        'form_data': form_data,
    })


def faq(request):
    return render(request, 'store/faq.html', {'faqs': FAQ_ITEMS})


def _policy_view(request, key):
    data = POLICY_CONTENT.get(key, {})
    return render(request, 'store/policy.html', {
        'page_title': data.get('title', 'Policy'),
        'content': data.get('content', ''),
    })


def shipping_policy(request):
    return _policy_view(request, 'shipping')


def returns_policy(request):
    return _policy_view(request, 'returns')


def privacy_policy(request):
    return _policy_view(request, 'privacy')


def terms(request):
    return _policy_view(request, 'terms')


def register(request):
    if request.user.is_authenticated:
        return redirect('store:home')

    if request.method == 'POST':
        form = CustomerRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, f'Welcome to Vayunandhan Crafts, {user.first_name}! 🎀')
            return redirect('store:home')
    else:
        form = CustomerRegistrationForm()

    return render(request, 'store/register.html', {'form': form})
