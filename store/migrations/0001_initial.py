from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('auth', '0012_alter_user_first_name_max_length'),
    ]

    operations = [
        migrations.CreateModel(
            name='Category',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=100, unique=True)),
                ('slug', models.SlugField(blank=True, max_length=120, unique=True)),
                ('description', models.TextField(blank=True)),
                ('image', models.ImageField(blank=True, null=True, upload_to='categories/')),
                ('is_active', models.BooleanField(default=True)),
                ('sort_order', models.PositiveSmallIntegerField(default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={'verbose_name_plural': 'categories', 'ordering': ['sort_order', 'name']},
        ),
        migrations.CreateModel(
            name='Product',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=255)),
                ('slug', models.SlugField(blank=True, max_length=280, unique=True)),
                ('sku', models.CharField(max_length=100, unique=True)),
                ('description', models.TextField(blank=True)),
                ('selling_price', models.DecimalField(decimal_places=2, max_digits=10)),
                ('original_price', models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True)),
                ('cost_price', models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True)),
                ('stock', models.PositiveIntegerField(default=0)),
                ('low_stock_threshold', models.PositiveIntegerField(default=5)),
                ('status', models.CharField(choices=[('active', 'Active'), ('inactive', 'Inactive')], default='active', max_length=20)),
                ('is_featured', models.BooleanField(default=False)),
                ('is_new_arrival', models.BooleanField(default=False)),
                ('is_best_seller', models.BooleanField(default=False)),
                ('weight_grams', models.PositiveIntegerField(default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('category', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='products', to='store.category')),
            ],
            options={'ordering': ['-created_at']},
        ),
        migrations.CreateModel(
            name='ProductImage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('image', models.ImageField(upload_to='products/')),
                ('alt_text', models.CharField(blank=True, max_length=255)),
                ('is_primary', models.BooleanField(default=False)),
                ('sort_order', models.PositiveSmallIntegerField(default=0)),
                ('product', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='images', to='store.product')),
            ],
            options={'ordering': ['-is_primary', 'sort_order']},
        ),
        migrations.CreateModel(
            name='StockMovement',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('quantity_change', models.IntegerField()),
                ('reason', models.CharField(choices=[('sale','Sale'),('restock','Restock'),('adjustment','Manual Adjustment'),('return','Return / Refund'),('reserved','Reserved'),('release','Reservation Released')], max_length=20)),
                ('note', models.CharField(blank=True, max_length=255)),
                ('order_reference', models.CharField(blank=True, max_length=60)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('performed_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='auth.user')),
                ('product', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='stock_movements', to='store.product')),
            ],
            options={'ordering': ['-created_at']},
        ),
        migrations.CreateModel(
            name='StoreSettings',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('store_name', models.CharField(default='Vayunandhan Crafts', max_length=100)),
                ('tagline', models.CharField(blank=True, max_length=200)),
                ('logo', models.ImageField(blank=True, null=True, upload_to='branding/')),
                ('favicon', models.ImageField(blank=True, null=True, upload_to='branding/')),
                ('email', models.EmailField(blank=True)),
                ('phone', models.CharField(blank=True, max_length=20)),
                ('whatsapp_number', models.CharField(blank=True, max_length=20)),
                ('instagram_url', models.URLField(blank=True)),
                ('facebook_url', models.URLField(blank=True)),
                ('address', models.TextField(blank=True)),
                ('upi_id', models.CharField(blank=True, max_length=100)),
                ('upi_display_name', models.CharField(blank=True, max_length=100)),
                ('upi_qr_code', models.ImageField(blank=True, null=True, upload_to='branding/')),
                ('upi_payment_instructions', models.TextField(blank=True, default='Scan the QR code or use the UPI ID to complete your payment. Enter your transaction/reference number after payment.')),
                ('delivery_charge', models.DecimalField(decimal_places=2, default='0.00', max_digits=8)),
                ('free_delivery_above', models.DecimalField(decimal_places=2, default='499.00', max_digits=8)),
                ('notify_order_created', models.BooleanField(default=True)),
                ('notify_payment_confirmed', models.BooleanField(default=True)),
                ('notify_order_dispatched', models.BooleanField(default=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={'verbose_name': 'Store Settings', 'verbose_name_plural': 'Store Settings'},
        ),
        migrations.CreateModel(
            name='CustomerProfile',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('phone', models.CharField(blank=True, max_length=20)),
                ('default_address_line1', models.CharField(blank=True, max_length=255)),
                ('default_address_line2', models.CharField(blank=True, max_length=255)),
                ('default_city', models.CharField(blank=True, max_length=100)),
                ('default_state', models.CharField(blank=True, max_length=100)),
                ('default_pincode', models.CharField(blank=True, max_length=10)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='profile', to='auth.user')),
            ],
        ),
        migrations.AddIndex(model_name='category',    index=models.Index(fields=['slug'], name='store_cat_slug_idx')),
        migrations.AddIndex(model_name='product',     index=models.Index(fields=['slug'], name='store_prod_slug_idx')),
        migrations.AddIndex(model_name='product',     index=models.Index(fields=['status', 'stock'], name='store_prod_status_idx')),
        migrations.AddIndex(model_name='product',     index=models.Index(fields=['category', 'status'], name='store_prod_cat_idx')),
        migrations.AddIndex(model_name='product',     index=models.Index(fields=['is_featured'], name='store_prod_featured_idx')),
    ]
