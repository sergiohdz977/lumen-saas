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
- Step 19 - Docker Compose: `Dockerfile` (python:3.13-slim + gunicorn), `docker-compose.yml` with 4 services (web, db=postgres:16-alpine, redis:7-alpine, celery worker), healthchecks, persistent volumes (`postgres_data`, `media_data`); settings gain env-driven `DJANGO_SECRET_KEY`/`DJANGO_DEBUG`/`DJANGO_ALLOWED_HOSTS` and a `USE_POSTGRES=1` switch (local/tests stay on SQLite); `psycopg[binary]==3.3.1` + `gunicorn==26.2.0` in requirements (205 passing total; container run pending Docker Desktop install)
- Next: verify `docker compose up --build` locally, then step 20 - production deployment




