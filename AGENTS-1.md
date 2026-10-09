# Lumen: project context for AI assistants

## What this project is
Lumen is a backend API (Django REST Framework) for a photography marketplace and management tool.
Photographers manage their clients, bookings and photo deliveries. Customers can browse
photographer profiles and catalogs and request a booking.

Two goals:
1. Portfolio project for a junior backend developer (clean, tested, explainable code).
2. Possible real product for the Cuban market, so it must stay adaptable to that context.

We build the WHOLE project, phase by phase, following the roadmap below. Deployment is done at the end.

## How to work with me (most important section)
- I am learning. I want to understand every step, not just get the result.
- Work ONE step of the roadmap at a time. Before each step:
  1. Say what the step is and why it is needed.
  2. Explain the concepts involved in simple terms.
  3. Show the plan (files to create or change) and wait for my OK.
- After each step: explain what the code does line by line, tell me how to test it, and tell me
  what the next step is.
- Do not jump ahead to later steps or phases, and do not add libraries before their step.
- Prefer me writing the core logic (models, permissions, tests). Offer hints first, code second.
  Write repetitive or boilerplate code only if I ask.
- Point out mistakes, security risks and bad practices honestly, including in my own code.
- Use plan mode first when a step touches many files.
- Code, comments, commits and docs are in English. Talk to me in Spanish.

## Language rules (for the product)
- Everything internal stays in English: model names, field names, API keys and routes
  (`photographer`, `created_at`, `/api/clients/`), stored values (`booked`, `editing`, `delivered`).
- Everything the end user sees is in Spanish: error messages, emails, display labels.
- Set `LANGUAGE_CODE = "es"`.
- Choices keep an English stored value and a Spanish label, for example
  `PHOTOGRAPHER = "photographer", "Fotógrafo"`.
- Use `verbose_name` in Spanish only where useful (admin).

## Actors and roles
- **Photographer**: creates a profile, catalog and packages, handles booking requests and shoots.
- **Customer**: browses photographers, sends booking requests, views delivered galleries.

Both are the same custom `users.User` (extends `AbstractUser`) with a `role` field
(`photographer` or `customer`, default `customer`). Role is chosen at registration; admin roles
must never be selectable by the user. Use a custom permission `IsPhotographer`
(`users/permissions.py`) for photographer-only endpoints.

## Business flow
1. Photographer registers and creates a profile, portfolio photos and packages (title, price).
2. Customer browses profiles (filter by city and shoot type) and picks a package.
3. Customer sends a `BookingRequest` with a date and message. Status: `pending`.
4. Photographer accepts or rejects it. On accept, a `Shoot` is created (status `booked`) and the
   customer is added to the photographer's `Client` list.
5. A deposit is paid to confirm the date.
6. After the session the shoot status becomes `editing`.
7. Photographer uploads photos to a private gallery. Customer views, favorites and downloads them.
   Shoot status becomes `delivered`.
8. Customer leaves a `Review`.

## Business rules
- Catalog and photographer profiles are public and read-only for everyone.
- A photographer only sees their own clients, shoots and incoming requests.
- A customer only sees their own requests and galleries.
- A photographer cannot accept a request for a date where they already have a shoot.
- Only the customer of a `delivered` shoot can leave a review.
- Gallery photos are private: only the photographer and that shoot's customer can access them.

## Monetization
- Customers use the app for free.
- Photographers pay: monthly subscription (free tier with limits, paid tier with more storage)
  and possibly a commission per paid booking.
- The deposit paid by the customer goes to the photographer, not to the app.
- Payments live in an isolated `payments` module so the provider can be swapped. Stripe does not
  operate in Cuba; for that market a local provider (for example EnZona, which has a payments API)
  or manual payments would be needed. Provider is not decided yet.

## Market constraints (Cuba)
- Internet is slow, expensive and limited: keep photos light (thumbnails, compression).
- Some cloud services may restrict access from Cuba. Verify before choosing providers.
- Do not build Cuba-specific logic yet. Keep the design generic and adaptable.

## Tech stack
- Python, Django, Django REST Framework
- JWT auth with `djangorestframework-simplejwt`
- Custom user model (`AUTH_USER_MODEL = "users.User"`)
- SQLite locally, PostgreSQL in production (`dj-database-url`, `DATABASE_URL`), on Railway or Neon
- Cloudflare R2 with `django-storages` and signed URLs for photos
- Celery + Redis for thumbnails and emails
- Django Channels (WebSockets), Docker, a payments provider

The ORM is Django's own. Do not suggest Prisma or other ORMs. Introduce each tool only at its step.

## Project structure
```
config/     settings and main urls
users/      custom User with role, register, login, permissions
clients/    photographer's clients
shoots/     photo sessions with status
profiles/   photographer profile, packages, portfolio
bookings/   booking requests
galleries/  galleries, photos, reviews
payments/   payment provider integration
```

## Models
- `User`: AbstractUser plus `role`
- `Client`: photographer (FK to User), user (FK to User, nullable), name, email, phone, created_at
- `Shoot`: client (FK), title, shoot_type, date, status (`booked`, `editing`, `delivered`), created_at
- `PhotographerProfile`: user (OneToOne), studio_name, slug (unique), bio, city, specialties,
  phone, is_published, created_at
- `Package`: profile (FK), title, description, price
- `PortfolioPhoto`: profile (FK), image, caption
- `BookingRequest`: customer (FK), package (FK), date, message, status
  (`pending`, `accepted`, `rejected`)
- `Gallery`, `Photo`, `Review`

## Roadmap (follow in order, one step at a time)

### Phase 1: base
1. Add `role` to User (migration) and include it in registration
2. `IsPhotographer` permission
3. `clients` module: serializer, viewset filtered by user, urls
4. `shoots` module: serializer, viewset, status, urls
5. Tests for users, clients and shoots, especially permissions

### Phase 2: marketplace
6. `profiles`: `PhotographerProfile` with slug, public read-only endpoints
7. `Package` and `PortfolioPhoto` (text fields first, images later)
8. Search and filters (city, specialty), pagination
9. `bookings`: create, list, accept and reject `BookingRequest`
10. Accepting a request creates the `Shoot` and the `Client`, with a date-conflict check
11. Tests for the marketplace and booking rules

### Phase 3: photos and background work
12. `galleries`: `Gallery` and `Photo` models, private access rules
13. Upload to Cloudflare R2 with signed URLs
14. Private gallery link for the customer
15. Celery + Redis: thumbnails with Pillow
16. Emails: booking confirmation and gallery delivery
17. Favorites and downloads, `Review` model
18. Tests for uploads and permissions

### Phase 4: advanced
19. Docker and Docker Compose (Django, PostgreSQL, Redis, Celery)
20. WebSockets with Channels (upload progress, notifications)
21. `payments` module: deposits, webhooks, payment states
22. Subscription plans for photographers

### Final
23. Switch to PostgreSQL, production settings, environment variables
24. Deploy (Railway or the chosen host)
25. README with screenshots, API docs, install steps, CHANGELOG cleanup
26. Clean code and verify the project runs from scratch

## Current state
- Done: Phase 1 complete + Phase 2 complete (steps 6-11) — `profiles` (public read-only,
  filters, pagination), `Package`/`PortfolioPhoto`, `bookings` (create, role-based lists,
  `accept`/`reject` with `Client` + `Shoot` creation and same-day conflict check),
  `Client.user` FK, marketplace integration tests (110 tests passing).
- Now: Phase 3, step 12 — `galleries`: `Gallery` and `Photo` models, private access rules.

## Conventions
- Each app owns its models, serializers, views, urls and tests.
- Views filter querysets by the authenticated user; never trust ids sent by the client.
- Write tests for every endpoint, especially permissions (user A must not see user B's data).
- Secrets live in `.env` (never committed). Keep `.env.example` with names only.
- After finishing each step, update `CHANGELOG.md` (dated log), the "Current state" section of
  this file, and `README.md` when something user-facing changes.
- Commit messages: short, English, imperative (for example `Add client endpoints`).
