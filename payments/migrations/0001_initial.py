from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('auth', '0012_alter_user_first_name_max_length'),
        ('orders', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Payment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('method', models.CharField(choices=[('razorpay','Razorpay'),('upi_manual','Manual UPI')], max_length=20)),
                ('amount', models.DecimalField(decimal_places=2, max_digits=10)),
                ('currency', models.CharField(default='INR', max_length=5)),
                ('status', models.CharField(choices=[('pending','Pending'),('verification_pending','Verification Pending'),('verified','Verified / Paid'),('failed','Failed'),('cancelled','Cancelled'),('refunded','Refunded')], default='pending', max_length=30)),
                ('razorpay_order_id', models.CharField(blank=True, max_length=100)),
                ('razorpay_payment_id', models.CharField(blank=True, max_length=100)),
                ('razorpay_signature', models.CharField(blank=True, max_length=255)),
                ('last_webhook_event_id', models.CharField(blank=True, max_length=100)),
                ('admin_note', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('verified_at', models.DateTimeField(blank=True, null=True)),
                ('order', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='payments', to='orders.order')),
                ('verified_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='verified_payments', to='auth.user')),
            ],
            options={'ordering': ['-created_at']},
        ),
        migrations.CreateModel(
            name='UpiPaymentDetail',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('upi_transaction_id', models.CharField(blank=True, max_length=100)),
                ('screenshot', models.ImageField(blank=True, null=True, upload_to='upi_screenshots/')),
                ('submitted_at', models.DateTimeField(auto_now_add=True)),
                ('payment', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='upi_detail', to='payments.payment')),
            ],
        ),
        migrations.AddIndex(model_name='payment', index=models.Index(fields=['order'], name='payments_pay_order_idx')),
        migrations.AddIndex(model_name='payment', index=models.Index(fields=['razorpay_order_id'], name='payments_pay_rz_idx')),
        migrations.AddIndex(model_name='payment', index=models.Index(fields=['status'], name='payments_pay_status_idx')),
    ]
