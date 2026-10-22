## 2026-10-01
- Created Django project with apps: users, clients, shoots
- Added Client and Shoot models
- Added .gitignore
- Next: build auth (register and login)


## 2026-10-02
- Added custom User model (AbstractUser)
- Added JWT auth: register, login, refresh
- Next: clients module (CRUD with per-user permissions)

## 2026-10-05
- Added `role` field to User (`photographer` / `customer`, default `customer`)
- Included `role` in the registration payload
- Registered User in Django admin with role filter
- Fixed JWT refresh URL (`/api/auth/token/refresh/`)
- Added `IsPhotographer` permission and tests (6 passing)
- Added `clients` module: serializer, viewset, urls, admin and tests (17 passing total)
- Added `shoots` module: state machine (`booked -> editing -> delivered`), ownership validation, tests (31 passing total)
- Added auth endpoint tests: register, login, refresh (42 passing total)
- Phase 1 complete
- Added `profiles` module: `PhotographerProfile` (OneToOne, auto-slug, `is_published`),
  public read-only endpoints at `/api/profiles/{slug}/`, moved `studio_name`/`phone` from
  `User` to profile (51 passing total)
- Added `Package` and `PortfolioPhoto` (text fields first): public read endpoints, photographer
  CRUD on own catalog, dynamic permissions, `?profile=` filter (73 passing total)
- Added profile filters (`?city=`, `?specialty=`), global pagination (10/page), stable ordering
  on all list endpoints (81 passing total)
- Added `bookings` module: `BookingRequest` (pending/accepted/rejected), customer create,
  role-based lists, custom `accept`/`reject` actions, `IsCustomer` permission (97 passing total)
- Accepting a booking now creates the `Client` (reused by email per photographer) and a `Shoot`
  with status `booked`, with a same-day conflict check and atomic transaction (103 passing total)
- Added `Client.user` FK (nullable, `SET_NULL`) with a unique `(photographer, user)` constraint:
  bookings link the customer account server-side (107 passing total)
- Added marketplace integration tests (full journey: register â†’ profile â†’ package â†’ book â†’
  accept â†’ shoot states; rejected-booking retry; package `profile` spoof regression)
  â€” Phase 2 complete (110 passing total)
- Added `galleries` module: `Gallery` (OneToOne per shoot, manual creation) and `Photo`
  (placeholder URL), private access (photographer CRUD own / customer read-only own),
  Spanish unique-validator message (129 passing total)
- Added gallery filters `?shoot=` and `?gallery=` (131 passing total)
- Step 13 â€” real photo uploads: `Photo.image` accepts a file (`multipart`), stored in
  Cloudinary when credentials are configured (`.env`) with automatic local fallback;
  tests isolated from the network (132 passing total)
- Step 14 - private gallery share links: photographer generates a signed expiring link (`POST /api/galleries/{id}/share-link/`); anyone with the link opens gallery + photos without login at `GET /api/gallery-view/<token>/` (7-day expiry, tamper-proof HMAC token; `client_username` now null-safe for clients without an account) (140 passing total)
- Step 15 - background thumbnails: Celery + Redis/Memurai broker, `Photo.thumbnail` field, `generate_thumbnail` task (Pillow resize to 400px, fired on upload and on image replace, failures logged never raised); tests run tasks eagerly with no broker (146 passing total)
- Step 16 - emails in background (Celery): booking accepted confirmation to the customer; gallery delivered email with private share link; console backend in dev (prints to terminal), locmem in tests; fixed bogus MAILERS setting into real EMAIL_BACKEND (153 passing total)
- Step 17a - favorites and downloads: `Favorite` model (unique photo+user, customer-only endpoints, own-gallery validation) and atomic `download_count` increments via `POST /api/photos/{id}/download/` (166 passing total)
- Step 17c - photo variants: HD `preview` (1280px) generated together with the thumbnail in one Celery task; downloads accept a version (`light` or `original`) with separate counters (169 passing total)
- Step 17d - favorites visibility: photographers list client favorites on their own photos (with customer username and thumbnail, `?photo=` filter); deleting stays customer-only (174 passing total)
- Step 17b - `Review` model: new `reviews` app; customers rate photographers 1-5 with comment (Spanish validator messages, one review per customer+photographer, only for photographers they worked with), role-based lists (written vs received) with `?photographer=` filter, admin registered (189 passing total)
- Step 18 - uploads and permissions audit: Spanish messages for `role` and photo `image` validation, plus 16 hardening tests (invalid/unknown ids, empty files, anonymous uploads and share links, portfolio spoof, forced booking status, shoot detail for customers) (205 passing total)
- Step 19 - Docker Compose: files written (commit a846525) but reverted and postponed to the end of the project due to slow internet; restore with `git revert aa9defd` when ready. Local/tests remain on SQLite, unchanged
- Step 20 - notifications: new `notifications` app (`Notification` model, REST history with read/read-all, WebSocket at `/ws/notifications/` with JWT-in-query or session auth, `notify()` helper); live pushes on booking accept, gallery delivery and new review; ASGI config with origin validator; channels + channels-redis + daphne added (216 passing total)
- Language switch - product is now English-first (pivot away from the Cuba market): all user-facing strings (validation errors, emails, notification texts, choice labels) converted to English, tests updated, AGENTS-1 language rules rewritten; Stripe chosen as the payment provider (216 passing total)
- Step 21 - payments: new `payments` app (Stripe Checkout deposits, 20% of the package price, `DEPOSIT_PERCENTAGE` setting); `Payment` model (pending/paid, amount in cents, unique session id), thin `providers.py` swap layer, signed webhook with idempotency, notifications on payment, role-based list (customer vs photographer); stripe==16.0.0 added (230 passing total)
- Step 21b - Stripe Connect: photographers onboarding (`POST /api/payments/onboard/` -> Express account + hosted form, `stripe_account_id`/`stripe_onboarded` on the profile, `account.updated` webhook), deposits become destination charges (money flows customer -> photographer, optional `STRIPE_PLATFORM_FEE_PERCENTAGE` platform fee), checkout blocked until onboarding completes (239 passing total)
- Step 22 - subscriptions: `plan` (free/pro) + `stripe_customer_id`/`subscription_id` on the profile, `POST /api/payments/upgrade/` (Checkout mode=subscription, needs `STRIPE_PRO_PRICE_ID`), webhook syncs `customer.subscription.updated/deleted` -> plan, Free tier limits enforced on gallery/photo creation (3 galleries / 100 photos, `FREE_TIER_*` settings, Pro unlimited), `plan` public in profile responses (254 passing total)
- Step 23 - production settings: PostgreSQL via `POSTGRES_*` env vars (psycopg 3.3.1, SQLite fallback for dev/tests), `DJANGO_SECRET_KEY`/`DJANGO_DEBUG`/`DJANGO_ALLOWED_HOSTS`/`DJANGO_CSRF_TRUSTED_ORIGINS` from env, production hardening when DEBUG=0 (refuses insecure key, secure cookies, TLS proxy header, optional SSL redirect/HSTS); .env.example and README updated; verified with the full suite on PostgreSQL 18
- Step 24 - deploy prep: `Procfile` (Daphne web on $PORT + release migrations), Celery worker documented as second service, `DATABASE_URL` support (Railway/Neon/Render), WhiteNoise static files (collectstatic verified), `docs/DEPLOY.md` step-by-step Railway guide (env vars, Stripe production webhook, Cloudinary requirement)
- Next: step 25 - README with screenshots, API docs, CHANGELOG cleanup




