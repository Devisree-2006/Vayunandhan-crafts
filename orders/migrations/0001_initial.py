from django.db import migrations, models
import django.db.models.deletion
import orders.models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('auth', '0012_alter_user_first_name_max_length'),
        ('store', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Order',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('reference', models.CharField(default=orders.models._order_ref, editable=False, max_length=20, unique=True)),
                ('customer_name', models.CharField(max_length=200)),
                ('customer_email', models.EmailField()),
                ('customer_phone', models.CharField(max_length=20)),
                ('address_line1', models.CharField(max_length=255)),
                ('address_line2', models.CharField(blank=True, max_length=255)),
                ('city', models.CharField(max_length=100)),
                ('state', models.CharField(max_length=100)),
                ('pincode', models.CharField(max_length=10)),
                ('delivery_instructions', models.TextField(blank=True)),
                ('subtotal', models.DecimalField(decimal_places=2, default='0.00', max_digits=10)),
                ('delivery_charge', models.DecimalField(decimal_places=2, default='0.00', max_digits=8)),
                ('discount_amount', models.DecimalField(decimal_places=2, default='0.00', max_digits=10)),
                ('total_amount', models.DecimalField(decimal_places=2, default='0.00', max_digits=10)),
                ('status', models.CharField(choices=[('placed','Order Placed'),('payment_pending','Payment Pending'),('payment_verification_pending','Payment Verification Pending'),('payment_verified','Payment Verified'),('processing','Processing'),('packed','Packed'),('dispatched','Dispatched'),('out_for_delivery','Out for Delivery'),('delivered','Delivered'),('cancelled','Cancelled'),('refund_pending','Refund Pending'),('refunded','Refunded')], default='placed', max_length=40)),
                ('admin_note', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='orders', to='auth.user')),
            ],
            options={'ordering': ['-created_at']},
        ),
        migrations.CreateModel(
            name='OrderItem',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('product_name', models.CharField(max_length=255)),
                ('product_sku', models.CharField(blank=True, max_length=100)),
                ('unit_price', models.DecimalField(decimal_places=2, max_digits=10)),
                ('original_price', models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True)),
                ('quantity', models.PositiveIntegerField(default=1)),
                ('item_discount', models.DecimalField(decimal_places=2, default='0.00', max_digits=10)),
                ('order', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='items', to='orders.order')),
                ('product', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='order_items', to='store.product')),
            ],
        ),
        migrations.CreateModel(
            name='OrderStatusHistory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('from_status', models.CharField(blank=True, max_length=40)),
                ('to_status', models.CharField(max_length=40)),
                ('note', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('changed_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='auth.user')),
                ('order', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='history', to='orders.order')),
            ],
            options={'ordering': ['created_at']},
        ),
        migrations.CreateModel(
            name='Shipment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('courier_name', models.CharField(blank=True, max_length=100)),
                ('awb_number', models.CharField(blank=True, max_length=100, verbose_name='AWB / Tracking No.')),
                ('tracking_url', models.URLField(blank=True)),
                ('dispatch_date', models.DateField(blank=True, null=True)),
                ('delivery_date', models.DateField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('order', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='shipment', to='orders.order')),
            ],
        ),
        migrations.AddIndex(model_name='order', index=models.Index(fields=['reference'], name='orders_order_ref_idx')),
        migrations.AddIndex(model_name='order', index=models.Index(fields=['status'], name='orders_order_status_idx')),
        migrations.AddIndex(model_name='order', index=models.Index(fields=['customer_email'], name='orders_order_email_idx')),
        migrations.AddIndex(model_name='order', index=models.Index(fields=['customer_phone'], name='orders_order_phone_idx')),
        migrations.AddIndex(model_name='orderitem', index=models.Index(fields=['order'], name='orders_item_order_idx')),
    ]
