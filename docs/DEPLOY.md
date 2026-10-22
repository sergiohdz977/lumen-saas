# Deploy

Lumen runs anywhere that supports a Procfile (Railway, Render, Fly.io...).
**Recommended for a free, no-card deployment: Render (app) + Neon (database).**
Railway is kept below as the paid alternative.

## Option A — Render + Neon (free, no credit card)

`render.yaml` in the repo provisions everything (web, Celery worker, Redis)
as a Blueprint. The database lives in **Neon** (free tier, does not expire
like Render's free Postgres, which is deleted after 30 days).

### A1. Neon (database, ~5 min)

1. Sign up at [neon.tech](https://neon.tech) with GitHub (free tier, no card).
2. Create a project (e.g. `lumen`) → default region is fine.
3. Copy the **pooled** connection string (the one with `-pooler` and
   `?sslmode=require`), e.g.
   `postgresql://user:pass@ep-xxx-pooler.region.aws.neon.tech/neondb?sslmode=require`.
4. Save it somewhere safe — you paste it into Render in step A2.

### A2. Render (app, ~10 min)

1. Sign up at [render.com](https://render.com) with GitHub (free, no card).
2. **New + → Blueprint** → pick the `lumen-saas` repo. Render reads
   `render.yaml` and creates three services (all **Free** plan):
   - `lumen-api` (web, daphne; runs migrations on boot)
   - `lumen-worker` (Celery: thumbnails + emails)
   - `lumen-redis` (broker, 25 MB, in-memory)
3. In the **lumen-shared** env group fill:
   | Variable | Value |
   |----------|-------|
   | `DATABASE_URL` | the Neon pooled connection string |
   | `STRIPE_SECRET_KEY` | `sk_test_...` from `.env` |
   | the rest | leave empty for now (Cloudinary/webhook later) |
4. Deploy. Migrations run automatically on web boot; if the first deploy
   happened before `DATABASE_URL` was set, hit **Manual Deploy → Clear
   build cache & deploy**.
5. Note the public domain (e.g. `https://lumen-xxxx.onrender.com`) and set
   on the **lumen-api** service (then redeploy):
   - `DJANGO_ALLOWED_HOSTS` = `lumen-xxxx.onrender.com`
   - `DJANGO_CSRF_TRUSTED_ORIGINS` = `https://lumen-xxxx.onrender.com`
   - `SITE_URL` = `https://lumen-xxxx.onrender.com`
6. Verify: `GET /api/profiles/` → 200, register a user, `/api/docs/` loads.

### A3. After the first deploy

- **Cloudinary is mandatory for a demo**: Render's disk is wiped on every
  redeploy/spin-down, so photos stored locally disappear. Create a free
  Cloudinary account (no card) and set the three `CLOUDINARY_*` variables.
- **Stripe webhook**: Stripe Dashboard → Developers → Webhooks → add
  `https://<domain>/api/payments/webhook/` with events
  `checkout.session.completed`, `account.updated`,
  `customer.subscription.updated`, `customer.subscription.deleted` →
  paste the signing secret into `STRIPE_WEBHOOK_SECRET` → redeploy.
- **Pro plan price**: create a recurring monthly Price in Stripe
  (test mode) and set `STRIPE_PRO_PRICE_ID` (`price_...`).
- **Emails**: free Render blocks outbound SMTP (ports 465/587); email
  features stay on the console backend in the demo.

### A4. Free-plan behavior (expected, not bugs)

- The web service **spins down after 15 min idle**; first request after
  idle takes ~1 min (open it once before a demo to warm it up).
- Neon's compute also pauses when unused; the first query adds a few
  seconds.
- 750 free instance-hours/month: the worker alone uses ~720; keep the web
  service mostly spun down (normal for a demo).

## Option B — Railway (paid plans; 30-day trial without card)

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
