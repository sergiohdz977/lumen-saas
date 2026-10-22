# Changelog

All notable changes to Lumen, grouped by roadmap phase (the full roadmap
lives in `AGENTS-1.md`). Test counts in parentheses show the state of the
suite after each step.

## Phase 1 — Base (2026-10-01 → 2026-10-05)

- Created the Django project: apps `users`, `clients`, `shoots`; `.gitignore`
- Custom `User` (AbstractUser) with `role` (`photographer` / `customer`,
  default customer), included in registration, admin filter
- JWT auth: register, login, refresh (`/api/auth/token/refresh/`)
- `IsPhotographer` permission
- `clients` module and `shoots` module with the state machine
  (`booked → editing → delivered`) and ownership validation (42 passing)

## Phase 2 — Marketplace

- `profiles`: `PhotographerProfile` (OneToOne, auto-slug, `is_published`),
  public read-only endpoints at `/api/profiles/{slug}/`;
  `studio_name`/`phone` moved from `User` to profile (51)
- `Package` and `PortfolioPhoto`: public reads, photographer CRUD on their
  own catalog, `?profile=` filter (73)
- Filters (`?city=`, `?specialty=`), global pagination (10/page), stable
  ordering (81)
- `bookings`: `BookingRequest` (pending/accepted/rejected), customer create,
  role-based lists, `accept`/`reject` actions, `IsCustomer` (97)
- Accepting creates the `Client` (reused by email per photographer) and a
  `Shoot` (`booked`) with same-day conflict check and atomic transaction;
  `Client.user` FK with unique `(photographer, user)` (107)
- Marketplace integration tests (full journey; rejected-booking retry;
  package profile spoof regression) — Phase 2 complete (110)

## Phase 3 — Photos and background work

- `galleries`: `Gallery` (one per shoot) and `Photo`, private access
  (photographer CRUD own / customer read-only own) (129)
- Gallery filters `?shoot=` and `?gallery=` (131)
- Real photo uploads: `multipart` files, Cloudinary with local fallback,
  tests isolated from the network (132)
- Private share links: signed expiring token
  (`POST /api/galleries/{id}/share-link/`, public
  `GET /api/gallery-view/<token>/`, 7-day expiry) (140)
- Background thumbnails: Celery + Redis/Memurai, Pillow resize to 400px,
  failures logged; tests run eagerly with no broker (146)
- Emails in background: booking accepted + gallery delivered with share
  link; console backend in dev, locmem in tests (153)
- Favorites and atomic download counters (`POST /api/photos/{id}/download/`)
  (166)
- Photo variants: HD `preview` (1280px), separate `light`/`original`
  counters (169)
- Favorites visibility: photographers see client favorites on their photos;
  deleting stays customer-only (174)
- `reviews` app: 1-5 ratings with comment, one per customer+photographer,
  only for photographers they worked with, role-based lists (189)
- Uploads and permissions audit: validation messages + 16 hardening tests
  (invalid ids, empty files, anonymous access, spoofing attempts) (205)

## Phase 4 — Advanced

- Docker Compose written (commit `a846525`) but **reverted and postponed**
  (`aa9defd`) due to slow internet; restore with `git revert aa9defd` (205)
- Notifications: `notifications` app, REST history with read/read-all,
  WebSocket at `/ws/notifications/` (JWT in query string or session),
  `notify()` helper; live pushes on booking accept, gallery delivery and new
  review; ASGI + origin validator; channels + daphne (216)
- **Language switch**: product is now English-first (pivot away from the
  Cuba market); all user-facing strings, labels and emails converted,
  tests updated; Stripe chosen as payment provider (216)
- Payments: `payments` app with Stripe Checkout deposits (20%,
  `DEPOSIT_PERCENTAGE`), `Payment` model (pending/paid, cents, unique
  session), thin `providers.py` swap layer, signed idempotent webhook,
  role-based lists (230)
- Stripe Connect: photographer onboarding (`POST /api/payments/onboard/` →
  Express account + hosted form), `stripe_account_id`/`stripe_onboarded`,
  `account.updated` webhook, destination charges with optional platform
  fee, checkout blocked until onboarded (239)
- Subscriptions: `plan` (free/pro) + `stripe_customer_id`/`subscription_id`,
  `POST /api/payments/upgrade/` (Checkout mode=subscription),
  `customer.subscription.updated/deleted` webhook syncs the plan, Free tier
  limits on gallery/photo creation (3 galleries / 100 photos; Pro
  unlimited), `plan` public in profile responses (254)

## Production and docs

- Production settings: PostgreSQL via `POSTGRES_*` env vars (psycopg 3.3.1,
  SQLite fallback for dev/tests), `DJANGO_SECRET_KEY`/`DJANGO_DEBUG`/
  `DJANGO_ALLOWED_HOSTS`/`DJANGO_CSRF_TRUSTED_ORIGINS`, production hardening
  on `DEBUG=0` (refuses the insecure key, secure cookies, TLS proxy header,
  optional SSL redirect/HSTS); full suite verified on PostgreSQL 18 (254)
- Deploy prep: `Procfile` (Daphne web on `$PORT` + release migrations),
  Celery worker as second service, `DATABASE_URL` support, WhiteNoise
  static files, step-by-step Railway guide in `docs/DEPLOY.md` (254)
- API docs: drf-spectacular with Swagger UI at `/api/docs/` and OpenAPI
  schema at `/api/schema/` (committed as `docs/api-schema.yml`); README
  rewritten (features, quick start, API docs, full endpoint reference);
  this changelog reorganized by phase (254)

## Next

- Step 26 — clean code and verify the project runs from scratch
- Step 19 — restore Docker (`git revert aa9defd`) before/with the final deploy
