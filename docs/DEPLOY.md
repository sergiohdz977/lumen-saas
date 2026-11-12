# Deploy (Railway)

Lumen runs on Railway with the GitHub repo connected. The stack is a web
service (Daphne, HTTP + WebSockets), a Celery worker (thumbnails and emails)
and the managed PostgreSQL + Redis plugins.

Live demo: <https://web-production-95133915.up.railway.app/>

## 1. Create the project

1. Railway -> **New Project** -> **Deploy from GitHub repo** -> pick
   `sergiohdz977/lumen-saas`.
2. **+ New** -> **Database** -> **Add PostgreSQL** (a `Postgres` service
   appears on the canvas).
3. **+ New** -> **Database** -> **Add Redis**.

## 2. Environment variables

Open the **web** service -> **Variables** and add:

| Variable | Value |
|----------|-------|
| `DJANGO_DEBUG` | `0` |
| `DJANGO_SECRET_KEY` | a real key, e.g. `python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"` |
| `DJANGO_ALLOWED_HOSTS` | `web-production-95133915.up.railway.app` (your domain) |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | `https://web-production-95133915.up.railway.app` |
| `SITE_URL` | `https://web-production-95133915.up.railway.app` |
| `DATABASE_URL` | **reference** to `Postgres` -> `DATABASE_URL` |
| `REDIS_URL` | **reference** to `Redis` -> `REDIS_URL` |
| `STRIPE_SECRET_KEY` | `sk_test_...` (test mode is enough to start) |
| `STRIPE_WEBHOOK_SECRET` | signing secret of the webhook (step 5) |
| `STRIPE_PRO_PRICE_ID` | monthly Price of the Pro plan (`price_...`) |
| `CLOUDINARY_CLOUD_NAME` / `CLOUDINARY_API_KEY` / `CLOUDINARY_API_SECRET` | Cloudinary dashboard credentials |

To add a reference: **+ New Variable** -> name it -> in the value field use
the reference icon and pick the service + variable. Do **not** paste the
Redis URL into `DATABASE_URL` (it must start with `postgresql://`).

## 3. Start command (migrations + static files)

Service -> **Settings** -> **Deploy** -> **Custom Start Command**:

```sh
python manage.py migrate --noinput && python manage.py collectstatic --noinput && daphne -b 0.0.0.0 -p $PORT config.asgi:application
```

`collectstatic` removes the `No directory at: /app/staticfiles/` warning;
WhiteNoise serves the admin assets from there.

## 4. Background worker (Celery)

Add a **second service** from the same repo with the same variables and
start command:

```bash
celery -A config worker -l info
```

Thumbnails, emails and other async work need it; the API works without it.

## 5. Stripe webhook

1. Stripe Dashboard -> Developers -> Webhooks -> **Add endpoint**:
   `https://<your-domain>/api/payments/webhook/`
2. Events: `checkout.session.completed`, `account.updated`,
   `customer.subscription.updated`, `customer.subscription.deleted`.
3. Copy the signing secret into `STRIPE_WEBHOOK_SECRET` and redeploy.

## 6. Cloudinary (recommended for a demo)

Railway's disk is wiped on every redeploy: uploaded photos disappear unless
they live in Cloudinary. Create a free account and set the three
`CLOUDINARY_*` variables.

## 7. Console (management commands)

Service **web** -> **Console** (SSH into the container; `python` is not on
`PATH`, the virtualenv lives in `/app/.venv`):

```bash
cd /app
.venv/bin/python manage.py createsuperuser
.venv/bin/python manage.py seed_demo        # demo photographers/packages/portfolio
.venv/bin/python manage.py reset_demo --yes # wipe customers/bookings/reviews, keep demo photographers
```

Demo photographers (password `DemoLumen2026`): `demofoto`, `elena.vargas`,
`marco.ortiz`, `aisha.khan`.

## Verify after deploy

```text
GET  https://<domain>/                      -> 200 (web frontend)
GET  https://<domain>/api/profiles/         -> 200 (paginated marketplace)
GET  https://<domain>/api/docs/             -> 200 (Swagger UI)
POST https://<domain>/api/auth/register/    -> 201
```

WebSockets: connect to `wss://<domain>/ws/notifications/?token=<jwt>`.

## Troubleshooting

- **`DisallowedHost`**: `DJANGO_ALLOWED_HOSTS` does not contain the Railway
  domain (add it and redeploy).
- **`settings.DATABASES is improperly configured`**: `DATABASE_URL` points to
  Redis or lacks the database name; use the Postgres reference.
- **502 / Application failed to respond**: check Deploy Logs; usually a
  missing `DJANGO_SECRET_KEY` with `DJANGO_DEBUG=0`, a failing migration or a
  bad start command.
- **`Unknown command`** in the console: the running deployment is older than
  the commit; redeploy and try again.
- **First request slow**: the app sleeps when idle; open the site once before
  a demo to warm it up.
