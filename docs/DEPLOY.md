# Deploy (Railway)

Lumen runs anywhere that supports a Procfile (Railway, Render, Fly.io...).
This guide targets **Railway** because it hosts the app, PostgreSQL and Redis
in one place and redeploys on every GitHub push.

## 1. Accounts

- GitHub account with this repository pushed.
- [railway.app](https://railway.app) account (paid plan needed to keep a
  service always on; card or PayPal required).
- Cloudinary account (uploaded photos must live in the cloud; the server
  disk is wiped on every deploy).
- Stripe account for payments (test mode is enough to start).

## 2. Create the project

1. Railway → **New Project** → **Deploy from GitHub repo** → pick
   `sergiohdz977/lumen-saas`.
2. **+ New** → **Database** → **PostgreSQL** (Railway stores the connection
   in `DATABASE_URL` for the app automatically).
3. **+ New** → **Redis** (Railway exposes it as `REDIS_URL`).
4. Railway detects the `Procfile`:
   - `web` runs Daphne (HTTP + WebSockets) on `$PORT`.
   - `release` runs migrations automatically on every deploy.

## 3. Environment variables

In the **app service → Variables**, add:

| Variable | Value |
|----------|-------|
| `DJANGO_DEBUG` | `0` |
| `DJANGO_SECRET_KEY` | generate one: `python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"` |
| `DJANGO_ALLOWED_HOSTS` | your Railway domain, e.g. `lumen.up.railway.app` |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | `https://lumen.up.railway.app` |
| `SITE_URL` | `https://lumen.up.railway.app` |
| `REDIS_URL` | set by the Redis plugin |
| `DATABASE_URL` | set by the PostgreSQL plugin |
| `STRIPE_SECRET_KEY` | Stripe test key (`sk_test_...`) |
| `STRIPE_WEBHOOK_SECRET` | signing secret of the webhook (step 5) |
| `STRIPE_PRO_PRICE_ID` | monthly Price of the Pro plan (`price_...`) |
| `CLOUDINARY_CLOUD_NAME` / `CLOUDINARY_API_KEY` / `CLOUDINARY_API_SECRET` | Cloudinary dashboard credentials |

## 4. Background worker (Celery)

Thumbnails and emails need a worker process. Add a **second service** from
the same repo with **Custom Start Command**:

```bash
celery -A config worker -l info
```

(On Linux the default process pool works; `--pool=solo` is Windows-only.)

## 5. Stripe webhook for production

1. Stripe Dashboard → Developers → Webhooks → **Add endpoint**:
   `https://<your-domain>/api/payments/webhook/`
2. Select events: `checkout.session.completed`, `account.updated`,
   `customer.subscription.updated`, `customer.subscription.deleted`.
3. Copy its **Signing secret** into `STRIPE_WEBHOOK_SECRET` and redeploy.

## 6. Nice to have

- **Custom domain** in Railway settings (the HTTPS certificate is automatic).
- **Superuser** for `/admin/`: Railway console → `python manage.py createsuperuser`.
- **Backups**: Railway Postgres keeps daily backups on paid plans; Neon is a
  free alternative if you prefer the database outside Railway (set its
  `DATABASE_URL` in the app variables).

## Verify after the first deploy

```text
GET  https://<domain>/api/profiles/     → 200 (paginated marketplace)
POST https://<domain>/api/auth/register/ → 201 (create an account)
```

WebSockets: connect to `wss://<domain>/ws/notifications/?token=<jwt>`.
