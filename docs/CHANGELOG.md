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

## Frontend — web app (vanilla HTML/CSS/JS)

- `frontend/`: index (public catalog, pagination, login/register modal),
  profile page (hero, packages, portfolio + lightbox, booking modal),
  dashboard (account, notifications, booking requests, shoots); no build
  step, served by Django itself
- `config/urls.py`: `page()` views for `/`, `/dashboard`, `/profile` and the
  `frontend_asset` route (`css|js|img/...`) with `Cache-Control: no-store`;
  asset cache-busting via `?v=2`
- CORS: allow any `localhost`/`127.0.0.1` port (`CORS_ALLOWED_ORIGIN_REGEXES`)
  so the frontend works from VS Code's preview or `runserver`
- Booking flow end to end: profile → "Book session" modal →
  `POST /api/bookings/` → toast + "Request sent ✓"; `IsCustomer` enforced
  client-side too
- Booking creation now notifies the photographer (`New booking request`) +
  `BookingNotificationTests`
- Dashboard: role-aware request lists (`profile_studio_name` on the booking
  serializer), Accept/Reject, shoots panel with `booked → editing → delivered`
  (confirm before "Mark delivered") and `client_name`/`client_email` on the
  shoot serializer
- `profiles/management/commands/seed_demo.py`: idempotent demo seed (4
  photographer profiles, 13 packages/photos, customer `sofia.reyes`,
  password `DemoLumen2026`)
- Portfolio placeholders: 13 wallpaper images resized 13.1 MB → 0.5 MB
  (960px, q78)
- `frontend/AGENTS.md` updated: English UI, Stripe as current provider,
  Cloudinary for storage, structure includes `notifications`/`reviews`/
  `frontend`/`docs` (257)

## Web frontend complete (2026-10-26)

- Shared `frontend/js/common.js`: auth header wiring, silent JWT refresh on
  401, JSON/error helpers, toasts, star ratings, session helpers (272)
- Marketplace: sign-up form with role picker (auto sign-in after register),
  search by city and specialty with `?city=`/`?specialty=` (272)
- Public profile: reviews section with average rating and "Write a review"
  modal for customers (eligibility errors from the API shown inline) (272)
- Dashboard: tabbed by role — overview, notifications (unread badge,
  mark read / mark all read), booking requests (accept, reject, pay deposit
  → Stripe checkout), shoots with gallery actions, catalog CRUD (packages and
  portfolio photos), studio profile form with publish toggle, clients,
  galleries (upload photos, delete, signed share link + copy), favorites,
  my reviews (edit/delete), payments (Connect onboarding, Pro upgrade,
  history) (272)
- Backend support: owner-only `PATCH /api/profiles/{slug}/` (create/delete
  stay 405), `user_id` + `is_published` in the profile payload, photographers
  list their own unpublished catalog items, `/api/auth/me/` returns
  `bio`/`phone`, `?unread=1` notification filter (272)
- Registering a photographer now auto-creates their unpublished profile (studio name = username, stable slug), so the studio panel works from the first login (272)
- `gallery.html` public share viewer (login required to download) and
  `payment-result.html` for the Stripe success/cancel return URLs (272)

## Payments flow and settings (2026-10-26)

- Deposits (20%) and balances (80%): accepting starts
  `accepted_pending_deposit` with a 48 h deadline — Celery auto-cancels
  expired bookings and notifies both parties; `Shoot.booking` backfilled for
  legacy accepts; balance checkout requires a confirmed booking with its
  gallery (322)
- `settle_payment` shared by webhook and success page, with
  `POST /api/payments/confirm-session/` fallback when no webhook secret is
  configured; deposit paid flips the booking to `confirmed` (322)
- Gallery paywall: customers get 403 on the original download and a masked
  preview until deposit + balance are paid; the photographer always has
  full quality (322)
- Dashboard: dynamic payments summary (pending count + total received/paid),
  customer deposit/balance buttons, red "Attention!" banner when the
  photographer is not onboarded plus one unread notification per blocked
  checkout attempt (322)
- Settings tab (was Profile, placed after Payments) with Public Profile /
  Account Details / Billing sections — Connect Stripe button, Upgrade to
  Pro hidden once the plan is Pro (322)

## Next

- Live deploy: create the Railway project and follow `docs/DEPLOY.md` (user)
- Step 19 — restore Docker (`git revert aa9defd`) before/with the final deploy
- Gallery/reviews UI on the web frontend
- Cloudinary for real photo uploads from the dashboard
- Post-roadmap backlog: real SMTP provider for production emails, CI with
  GitHub Actions, usage endpoint (galleries/photos quota), Stripe billing
  portal, Sentry
