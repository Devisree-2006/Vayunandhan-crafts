# Vayunandhan Crafts — E-Commerce Website

A complete, production-ready Django e-commerce store for **Vayunandhan Crafts** — handmade girls accessories, resin keychains, clay charms, scrunchies, hair clips, earrings, and personalised gift hampers.

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Project Structure](#project-structure)
3. [Quick Start (Local Development)](#quick-start-local-development)
4. [Environment Variables Reference](#environment-variables-reference)
5. [Database Setup](#database-setup)
6. [Creating the Admin Account](#creating-the-admin-account)
7. [Loading Sample Data](#loading-sample-data)
8. [Uploading Your Logo](#uploading-your-logo)
9. [Razorpay Integration](#razorpay-integration)
10. [Manual UPI Payment Setup](#manual-upi-payment-setup)
11. [WhatsApp Business API Setup](#whatsapp-business-api-setup)
12. [Email (SMTP) Configuration](#email-smtp-configuration)
13. [Running Tests](#running-tests)
14. [Production Deployment](#production-deployment)
15. [MySQL Configuration](#mysql-configuration)
16. [Static & Media Files](#static--media-files)
17. [Shiprocket (Future)](#shiprocket-future)
18. [Troubleshooting](#troubleshooting)

---

## Prerequisites

| Requirement | Version |
|---|---|
| Python | 3.11 or 3.13 |
| pip | latest |
| Git | any |
| (Production only) MySQL | 8.0+ |

---

## Project Structure

```
vayunandhan business/
├── manage.py
├── requirements.txt
├── .env               ← your local secrets (never commit)
├── .env.example       ← template to copy from
├── .gitignore
├── README.md
│
├── config/            ← Django project config
│   ├── settings.py
│   ├── urls.py
│   ├── wsgi.py
│   └── asgi.py
│
├── store/             ← Products, categories, pages
├── orders/            ← Cart, checkout, order tracking
├── payments/          ← Razorpay + Manual UPI
├── notifications/     ← Email + WhatsApp
├── dashboard/         ← Admin dashboard
│
├── templates/         ← All HTML templates
├── static/            ← CSS, JS, images
└── media/             ← Uploaded files (products, logos)
```

---

## Quick Start (Local Development)

### 1. Open PowerShell in the project folder

```powershell
cd "C:\Users\Pandu\Documents\vayunandhan business"
```

### 2. Create and activate virtual environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

> If you get a script execution error, run this **once**:
> ```powershell
> Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
> ```

### 3. Install dependencies

```powershell
pip install -r requirements.txt
```

### 4. Create your `.env` file

```powershell
Copy-Item .env.example .env
```

Open `.env` and set at minimum:
```
SECRET_KEY=replace-with-any-long-random-string
DEBUG=True
ALLOWED_HOSTS=127.0.0.1,localhost
```

### 5. Run migrations

```powershell
python manage.py makemigrations store
python manage.py makemigrations orders
python manage.py makemigrations payments
python manage.py makemigrations notifications
python manage.py makemigrations dashboard
python manage.py migrate
```

### 6. Create the superuser (admin account)

```powershell
python manage.py createsuperuser
```

Enter your username, email, and password when prompted.

### 7. Load sample data

```powershell
python manage.py seed_data
```

This creates all product categories, 16 sample products, and default store settings.

### 8. Start the development server

```powershell
python manage.py runserver
```

Open **http://127.0.0.1:8000** in your browser.

| URL | Description |
|---|---|
| http://127.0.0.1:8000 | Customer storefront |
| http://127.0.0.1:8000/dashboard/ | Admin dashboard |
| http://127.0.0.1:8000/django-admin/ | Django built-in admin |

---

## Environment Variables Reference

Copy `.env.example` to `.env` and fill in your values. **Never commit `.env` to Git.**

```ini
# ── Django Core ──────────────────────────────────────────────────────────────────
SECRET_KEY=your-very-secret-django-key-change-this
DEBUG=True
ALLOWED_HOSTS=127.0.0.1,localhost

# ── Database (leave blank for SQLite local dev) ───────────────────────────────────
DATABASE_URL=

# ── Razorpay ─────────────────────────────────────────────────────────────────────
RAZORPAY_KEY_ID=rzp_test_xxxxxxxxxxxxxx
RAZORPAY_KEY_SECRET=xxxxxxxxxxxxxxxxxxxxxxxx
RAZORPAY_WEBHOOK_SECRET=your_webhook_secret

# ── WhatsApp Business Cloud API ──────────────────────────────────────────────────
WHATSAPP_ACCESS_TOKEN=EAAxxxxxxx...
WHATSAPP_PHONE_NUMBER_ID=1234567890123
WHATSAPP_BUSINESS_ACCOUNT_ID=9876543210987
WHATSAPP_VERIFY_TOKEN=my_random_verify_token
WHATSAPP_APP_SECRET=app_secret_from_meta_dashboard

# ── Email SMTP ────────────────────────────────────────────────────────────────────
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=youremail@gmail.com
EMAIL_HOST_PASSWORD=your_app_password
DEFAULT_FROM_EMAIL=Vayunandhan Crafts <youremail@gmail.com>

# ── Store ─────────────────────────────────────────────────────────────────────────
STORE_NAME=Vayunandhan Crafts
STORE_EMAIL=hello@vayunandhan.com
STORE_PHONE=+91XXXXXXXXXX
STORE_WHATSAPP_NUMBER=91XXXXXXXXXX
STORE_UPI_ID=yourname@upi
STORE_INSTAGRAM=https://www.instagram.com/vayunandhan_crafts
```

---

## Database Setup

### SQLite (local development — default)

No extra setup needed. A `db.sqlite3` file is created automatically on first migrate.

### MySQL (production)

1. Create a database:
```sql
CREATE DATABASE vayunandhan_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'vc_user'@'localhost' IDENTIFIED BY 'strong_password';
GRANT ALL PRIVILEGES ON vayunandhan_db.* TO 'vc_user'@'localhost';
FLUSH PRIVILEGES;
```

2. Add to `.env`:
```ini
DB_ENGINE=django.db.backends.mysql
DB_NAME=vayunandhan_db
DB_USER=vc_user
DB_PASSWORD=strong_password
DB_HOST=localhost
DB_PORT=3306
```

3. Run migrations:
```powershell
python manage.py migrate
```

---

## Creating the Admin Account

```powershell
python manage.py createsuperuser
```

Log in at `/dashboard/` with these credentials to access the admin dashboard.

To make an existing user a staff member:
```powershell
python manage.py shell -c "from django.contrib.auth.models import User; u=User.objects.get(username='yourname'); u.is_staff=True; u.is_superuser=True; u.save()"
```

---

## Loading Sample Data

```powershell
python manage.py seed_data
```

Creates:
- 11 product categories (Gift Hampers, Hair Accessories, Scrunchies, Hair Clips, Earrings, Resin Keychains, Clay Charms, Customized Gifts, Handmade Crafts, New Arrivals, Sale & Offers)
- 16 sample products with prices, stock, and flags
- Default store settings (delivery charge ₹49, free above ₹499)

Run it again safely — it skips existing records.

---

## Uploading Your Logo

### Via Admin Dashboard (recommended)
1. Log in at `/dashboard/`
2. Go to **Settings**
3. Upload your logo under **Store Identity → Logo**
4. Save

### Via Django Admin
1. Go to `/django-admin/`
2. Open **Store Settings**
3. Upload logo and save

The logo automatically appears in the navbar, footer, emails, and login page.

---

## Razorpay Integration

### Test Mode Setup

1. Create a free account at [razorpay.com](https://razorpay.com)
2. Go to **Settings → API Keys → Generate Test Key**
3. Copy your `Key ID` and `Key Secret`
4. Add to `.env`:
```ini
RAZORPAY_KEY_ID=rzp_test_xxxxxxxxxxxxxx
RAZORPAY_KEY_SECRET=xxxxxxxxxxxxxxxxxxxxxxxx
```

### Webhook Setup

1. In Razorpay Dashboard → **Settings → Webhooks → Add New Webhook**
2. Set URL: `https://yourdomain.com/payments/razorpay/webhook/`
3. Select events: `payment.captured`, `payment.failed`
4. Set a webhook secret and add to `.env`:
```ini
RAZORPAY_WEBHOOK_SECRET=your_webhook_secret
```

### Live Mode

When you're ready to go live, replace test keys with live keys from Razorpay and set `DEBUG=False`.

---

## Manual UPI Payment Setup

1. Log in at `/dashboard/` → **Settings**
2. Fill in:
   - **UPI ID** — e.g. `yourname@upi`
   - **Display Name** — your name or business name
   - **UPI QR Code** — upload a screenshot of your UPI QR code
   - **Payment Instructions** — instructions shown to customers

Customers scan the QR code, pay, enter their transaction ID, and optionally upload a screenshot. You verify manually in the dashboard under **Payments**.

---

## WhatsApp Business API Setup

### Requirements
- A verified **Meta Business Account**
- An approved **WhatsApp Business Account**
- An active **phone number** registered with WhatsApp Business

### Step-by-step

1. Go to [Meta for Developers](https://developers.facebook.com/)
2. Create an App → Select **Business** type
3. Add **WhatsApp** product to your app
4. In the WhatsApp section, go to **API Setup**
5. Note your **Phone Number ID** and **WhatsApp Business Account ID**
6. Generate a **temporary access token** (or create a permanent system user token)
7. Add to `.env`:
```ini
WHATSAPP_ACCESS_TOKEN=EAAxxxxxxx...
WHATSAPP_PHONE_NUMBER_ID=1234567890123
WHATSAPP_BUSINESS_ACCOUNT_ID=9876543210987
WHATSAPP_VERIFY_TOKEN=any_random_string_you_choose
STORE_WHATSAPP_NUMBER=91XXXXXXXXXX
```

### Webhook Setup

1. In Meta Dashboard → **WhatsApp → Configuration → Webhook**
2. Set Callback URL: `https://yourdomain.com/notifications/whatsapp/webhook/`
3. Set Verify Token (must match `WHATSAPP_VERIFY_TOKEN` in `.env`)
4. Subscribe to `messages` and `message_status` fields

### Notification Toggles

Enable/disable each notification type in `/dashboard/` → **Settings → WhatsApp Notification Toggles**.

> **Note:** The current implementation sends free-form text messages to your business number.
> For sending messages to customers, you must create and get approved **Message Templates**
> in the Meta Business Manager. Template approval takes 1–3 business days.

---

## Email (SMTP) Configuration

### Local Development (console output)

Emails print to the terminal — no real sending:
```ini
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
```

### Gmail SMTP

1. Enable **2-Factor Authentication** on your Google account
2. Go to **Google Account → Security → App Passwords**
3. Create an App Password for "Mail"
4. Add to `.env`:
```ini
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=youremail@gmail.com
EMAIL_HOST_PASSWORD=your_16_char_app_password
DEFAULT_FROM_EMAIL=Vayunandhan Crafts <youremail@gmail.com>
```

### Other Providers

| Provider | HOST | PORT |
|---|---|---|
| Outlook/Hotmail | smtp-mail.outlook.com | 587 |
| Yahoo Mail | smtp.mail.yahoo.com | 587 |
| Zoho Mail | smtp.zoho.in | 587 |
| SendGrid | smtp.sendgrid.net | 587 |

---

## Running Tests

```powershell
python manage.py test
```

Run tests for a specific app:
```powershell
python manage.py test store
python manage.py test orders
python manage.py test payments
python manage.py test notifications
python manage.py test dashboard
```

Run with verbosity:
```powershell
python manage.py test --verbosity=2
```

> All tests use mocked external APIs (Razorpay, WhatsApp, SMTP).
> No real credentials are required to run the test suite.

---

## Production Deployment

### 1. Server requirements

- Ubuntu 22.04 LTS (recommended)
- Python 3.11+
- Nginx
- Gunicorn
- MySQL 8.0+
- SSL certificate (Let's Encrypt)

### 2. Clone and set up

```bash
git clone <your-repo-url> /var/www/vayunandhan
cd /var/www/vayunandhan
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Production `.env`

```ini
SECRET_KEY=long-random-production-key
DEBUG=False
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com

DB_ENGINE=django.db.backends.mysql
DB_NAME=vayunandhan_db
DB_USER=vc_user
DB_PASSWORD=strong_db_password
DB_HOST=localhost
DB_PORT=3306

EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
# ... (all other credentials)
```

### 4. Collect static files

```bash
python manage.py collectstatic --noinput
```

### 5. Run migrations

```bash
python manage.py migrate
python manage.py createsuperuser
python manage.py seed_data
```

### 6. Gunicorn service (`/etc/systemd/system/vayunandhan.service`)

```ini
[Unit]
Description=Vayunandhan Crafts Django App
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/var/www/vayunandhan
ExecStart=/var/www/vayunandhan/.venv/bin/gunicorn \
    --workers 3 \
    --bind unix:/run/vayunandhan.sock \
    config.wsgi:application
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable vayunandhan
sudo systemctl start vayunandhan
```

### 7. Nginx config (`/etc/nginx/sites-available/vayunandhan`)

```nginx
server {
    listen 80;
    server_name yourdomain.com www.yourdomain.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    server_name yourdomain.com www.yourdomain.com;

    ssl_certificate     /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;

    client_max_body_size 10M;

    location /static/ {
        alias /var/www/vayunandhan/staticfiles/;
        expires 30d;
    }

    location /media/ {
        alias /var/www/vayunandhan/media/;
        expires 7d;
    }

    location / {
        proxy_pass http://unix:/run/vayunandhan.sock;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/vayunandhan /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### 8. SSL Certificate (Let's Encrypt)

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d yourdomain.com -d www.yourdomain.com
```

### 9. Database Backups

Automate daily MySQL backups:
```bash
# Add to crontab: crontab -e
0 2 * * * mysqldump -u vc_user -pstrong_db_password vayunandhan_db > /backups/vayunandhan_$(date +\%Y\%m\%d).sql
```

---

## Static & Media Files

| Type | Local path | Served by |
|---|---|---|
| Static (CSS/JS) | `static/` | WhiteNoise (dev) / Nginx (prod) |
| Collected static | `staticfiles/` | Nginx (prod) |
| Media (uploads) | `media/` | Django (dev) / Nginx (prod) |

**Media subdirectories:**
- `media/products/` — product images
- `media/branding/` — logo, favicon, UPI QR code
- `media/categories/` — category images
- `media/upi_screenshots/` — customer payment screenshots

---

## Shiprocket (Future)

The codebase is architected to support Shiprocket integration. The `Shipment` model already stores:
- Courier name
- AWB / tracking number
- Tracking URL
- Dispatch and delivery dates

To add Shiprocket:
1. Add `SHIPROCKET_EMAIL` and `SHIPROCKET_PASSWORD` to `.env`
2. Create `store/shiprocket_service.py` using the [Shiprocket API docs](https://apidocs.shiprocket.in/)
3. Call it from `dashboard/views.py` in the dispatch workflow

---

## Troubleshooting

### `ModuleNotFoundError: No module named 'dotenv'`
```powershell
pip install python-dotenv
```

### `ModuleNotFoundError: No module named 'razorpay'`
```powershell
pip install razorpay
```

### Migrations out of sync
```powershell
python manage.py makemigrations
python manage.py migrate
```

### Static files not loading (development)
Make sure `DEBUG=True` in your `.env` and the dev server is running.

### Images not showing in production
Run `python manage.py collectstatic` and ensure Nginx serves `/media/` correctly.

### WhatsApp notifications not sending
1. Check `WHATSAPP_ACCESS_TOKEN` and `WHATSAPP_PHONE_NUMBER_ID` in `.env`
2. Check the `NotificationLog` table in Django Admin for error messages
3. Ensure your Meta App is in **Live mode** (not Development mode) for production

### Razorpay payment not completing
1. Verify `RAZORPAY_KEY_ID` and `RAZORPAY_KEY_SECRET` are correct
2. Check browser console for JS errors on the payment page
3. Check Django logs for signature verification errors
4. In test mode, use Razorpay test card: `4111 1111 1111 1111`, CVV: `123`, Expiry: any future date

### Emails going to spam
1. Set up SPF, DKIM, and DMARC records for your domain
2. Use a transactional email service (SendGrid, Mailgun) instead of Gmail for production
3. Ensure `DEFAULT_FROM_EMAIL` matches your verified sending domain

### Port 8000 already in use
```powershell
python manage.py runserver 8080
```
