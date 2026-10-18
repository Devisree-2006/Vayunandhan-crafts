"""
Management command: python manage.py seed_data
Creates sample categories, products, and store settings for development.
"""
from django.core.management.base import BaseCommand
from django.utils.text import slugify
from decimal import Decimal
from store.models import Category, Product, StoreSettings


CATEGORIES = [
    ('Gift Hampers',      'Beautifully curated handmade gift hampers for every occasion'),
    ('Hair Accessories',  'Cute and trendy hair accessories handcrafted with love'),
    ('Scrunchies',        'Soft, stylish scrunchies in every colour and pattern'),
    ('Hair Clips',        'Adorable hair clips for all hair types'),
    ('Earrings',          'Handmade earrings — light, fun, and stylish'),
    ('Resin Keychains',   'Custom resin keychains with embedded charms and glitter'),
    ('Clay Charms',       'Miniature clay charms — perfect for bags and gifts'),
    ('Customized Gifts',  'Personalised gifts made just for your loved ones'),
    ('Handmade Crafts',   'Assorted handmade crafts and decorative items'),
    ('New Arrivals',      'Fresh additions to our collection'),
    ('Sale & Offers',     'Special discounts and limited-time offers'),
]

PRODUCTS = [
    # (name, category_name, selling_price, original_price, stock, is_featured, is_new, is_best)
    ('Pastel Dream Scrunchie Set',        'Scrunchies',        199, 249, 25, True,  True,  False),
    ('Resin Galaxy Keychain',             'Resin Keychains',   149, 199, 18, True,  False, True),
    ('Floral Hair Clip Set of 6',         'Hair Clips',        249, None, 30, True, True,  False),
    ('Birthday Hamper – Pink Edition',    'Gift Hampers',      499, 599, 10, True,  False, True),
    ('Rainbow Clay Charm Pack',           'Clay Charms',       179, 249, 20, False, True,  False),
    ('Pearl Drop Earrings',               'Earrings',          129, 179, 15, False, False, True),
    ('Bestie Gift Hamper',                'Gift Hampers',      699, 799, 8,  True,  True,  True),
    ('Satin Bow Scrunchie',               'Scrunchies',        99,  None, 40, False, True, False),
    ('Custom Name Keychain',              'Customized Gifts',  249, None, 20, True,  False, False),
    ('Butterfly Hair Clips – Set of 4',  'Hair Clips',        199, 249, 22, False, True,  False),
    ('Glitter Resin Keychain',            'Resin Keychains',   169, 199, 16, False, False, True),
    ('Daisy Stud Earrings',               'Earrings',          99,  None, 25, False, True,  False),
    ('Friendship Day Hamper',             'Gift Hampers',      349, 449, 12, False, True,  False),
    ('Crochet Scrunchie Set of 3',        'Scrunchies',        159, None, 28, False, False, True),
    ('Mini Mushroom Clay Charm',          'Clay Charms',       79,  99,  50, False, True,  False),
    ('Personalized Keychain with Photo',  'Customized Gifts',  299, None, 15, True,  True,  False),
]


class Command(BaseCommand):
    help = 'Seed the database with sample categories and products.'

    def handle(self, *args, **options):
        self.stdout.write('Seeding store data…')

        # Store settings
        s = StoreSettings.get()
        if not s.store_name or s.store_name == 'Vayunandhan Crafts':
            s.store_name  = 'Vayunandhan Crafts'
            s.tagline     = 'Cute Gifts, Handmade with Love'
            s.delivery_charge      = Decimal('49.00')
            s.free_delivery_above  = Decimal('499.00')
            s.upi_payment_instructions = (
                'Scan the QR code or pay to the UPI ID shown above. '
                'Enter your transaction reference number after completing payment.'
            )
            s.save()
            self.stdout.write('  ✓ Store settings updated')

        # Categories
        cat_map = {}
        for name, desc in CATEGORIES:
            slug = slugify(name)
            cat, created = Category.objects.get_or_create(
                slug=slug,
                defaults={'name': name, 'description': desc, 'is_active': True}
            )
            cat_map[name] = cat
            if created:
                self.stdout.write(f'  ✓ Category: {name}')

        # Products
        for (pname, cname, price, orig, stock, featured, new_arr, best) in PRODUCTS:
            slug = slugify(pname)
            # ensure unique slug
            base_slug = slug
            n = 1
            while Product.objects.filter(slug=slug).exists():
                slug = f'{base_slug}-{n}'; n += 1

            sku = 'VC-' + slugify(pname)[:12].upper().replace('-', '')
            p, created = Product.objects.get_or_create(
                name=pname,
                defaults={
                    'slug': slug,
                    'sku': sku,
                    'category': cat_map.get(cname),
                    'description': f'A beautiful handmade {pname.lower()} crafted with love by Vayunandhan Crafts.',
                    'selling_price': Decimal(str(price)),
                    'original_price': Decimal(str(orig)) if orig else None,
                    'cost_price': Decimal(str(round(price * 0.4))),
                    'stock': stock,
                    'low_stock_threshold': 5,
                    'status': Product.STATUS_ACTIVE,
                    'is_featured': featured,
                    'is_new_arrival': new_arr,
                    'is_best_seller': best,
                }
            )
            if created:
                self.stdout.write(f'  ✓ Product: {pname}')

        self.stdout.write(self.style.SUCCESS(
            f'\nDone! {Category.objects.count()} categories, {Product.objects.count()} products.'
        ))
