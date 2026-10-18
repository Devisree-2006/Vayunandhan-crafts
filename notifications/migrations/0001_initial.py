from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('orders', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='NotificationLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('channel', models.CharField(choices=[('email','Email'),('whatsapp','WhatsApp')], max_length=20)),
                ('event', models.CharField(choices=[('order_placed','Order Placed'),('payment_confirmed','Payment Confirmed'),('payment_verification_pending','Payment Verification Pending'),('payment_rejected','Payment Rejected'),('order_dispatched','Order Dispatched'),('order_delivered','Order Delivered'),('order_cancelled','Order Cancelled'),('refunded','Refunded')], max_length=40)),
                ('recipient', models.CharField(max_length=255)),
                ('idempotency_key', models.CharField(max_length=100, unique=True)),
                ('status', models.CharField(choices=[('pending','Pending'),('sent','Sent'),('failed','Failed'),('skipped','Skipped')], default='pending', max_length=20)),
                ('error_message', models.TextField(blank=True)),
                ('attempts', models.PositiveSmallIntegerField(default=0)),
                ('sent_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('order', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='notifications', to='orders.order')),
            ],
            options={'ordering': ['-created_at']},
        ),
        migrations.AddIndex(model_name='notificationlog', index=models.Index(fields=['order', 'event', 'channel'], name='notif_log_order_idx')),
        migrations.AddIndex(model_name='notificationlog', index=models.Index(fields=['idempotency_key'], name='notif_log_idem_idx')),
        migrations.AddIndex(model_name='notificationlog', index=models.Index(fields=['status'], name='notif_log_status_idx')),
    ]
