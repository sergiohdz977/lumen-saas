# Lumen: project context for AI assistants

## What this project is
Lumen is a backend API (Django REST Framework) for a photography marketplace and management tool.
Photographers manage their clients, bookings and photo deliveries. Customers can browse
photographer profiles and catalogs and request a booking.

Two goals:
1. Portfolio project for a junior backend developer (clean, tested, explainable code).
2. Possible real product for the Cuban market, so it must be adaptable to that context.

## How to work with me (important)
- I am learning. Explain what you do and why, in simple terms.
- Small steps: one module at a time, finish and test it before the next.
- Use plan mode first. Do not write large amounts of code without asking.
- Do not add libraries or features that are not in the current phase.
- Code, comments, commits and docs are in English.

## Language rules
- Everything is in English: model names, field names, API routes
  (`photographer`, `created_at`, `/api/clients/`), stored values (`booked`, `editing`,
  `delivered`), and everything the end user sees (UI labels, emails, error messages).
- `LANGUAGE_CODE = "en-us"`.
- Choices keep the stored value and the label in English, for example
  `PHOTOGRAPHER = "photographer", "Photographer"`.
- `verbose_name` only where useful (admin).

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
- Payments go in an isolated `payments` module so the provider can be swapped.
  Current provider: Stripe (test keys in `.env`). Stripe does not operate in Cuba: for
  the Cuban market the module can later be swapped for a local provider (for example
  EnZona) or manual payments. Not for now.

## Market constraints (Cuba)
- Internet is slow, expensive and limited: keep photos light (thumbnails, compression).
- Some cloud services may restrict access from Cuba. Verify before choosing providers.
- Do not build Cuba-specific logic yet. Keep the design generic and adaptable.

## Tech stack
Current:
- Python, Django, Django REST Framework
- JWT auth with `djangorestframework-simplejwt`
- Custom user model (`AUTH_USER_MODEL = "users.User"`)
- SQLite locally

Later, only when we reach that phase:
- PostgreSQL in production (`dj-database-url`, `DATABASE_URL`), hosted on Neon
- Cloudinary for photo storage (the `PortfolioPhoto.image` URLField now; uploads later)
- Celery + Redis for thumbnails and emails
- Django Channels, Docker

The ORM is Django's own. Do not suggest Prisma or other ORMs.

## Project structure
```
config/         settings and main urls (also serves the frontend)
users/          custom User with role, register, login, permissions
clients/        photographer's clients
shoots/         photo sessions with status
profiles/       photographer profile, packages, portfolio
bookings/       booking requests
galleries/      galleries and photos
reviews/        customer reviews
notifications/  in-app notifications (REST + WebSocket) and email tasks
payments/       payment provider integration (Stripe, isolated)
frontend/       vanilla HTML/CSS/JS web app (index, profile, dashboard)
docs/           CHANGELOG and roadmap notes
```

## Models
- `User`: AbstractUser plus `role`
- `Client`: photographer (FK to User), name, email, phone, created_at
- `Shoot`: client (FK), title, shoot_type, date, status (`booked`, `editing`, `delivered`), created_at
- Phase 2:
  - `PhotographerProfile`: user (OneToOne), studio_name, slug (unique), bio, city, specialties,
    phone, is_published, created_at
  - `Package`: profile (FK), title, description, price
  - `PortfolioPhoto`: profile (FK), image, caption
  - `BookingRequest`: customer (FK), package (FK), date, message, status
    (`pending`, `accepted`, `rejected`)
- Phase 3: `Gallery`, `Photo`, `Review`
- `Notification`: user (FK), title, message, is_read, created_at

## Current state
- Done: all backend modules — auth/roles, clients, shoots state machine, profiles,
  packages, portfolio, bookings (accept/reject → shoot + client + notifications),
  galleries, reviews, notifications (REST + WebSocket + email), payments (Stripe,
  isolated). 257 passing tests.
- Done: web frontend in `frontend/` (vanilla HTML/CSS/JS): public catalog with
  pagination, photographer profile with packages/portfolio/lightbox/booking modal,
  JWT login, private dashboard with account, notifications, booking requests
  (accept/reject) and shoots (booked → editing → delivered). Served by Django on
  port 8000 (same origin as the API). Demo data via `manage.py seed_demo`.
- Next: gallery/reviews UI on the web, README/CHANGELOG catch-up, commit pending
  work, Cloudinary for real photo uploads.

## Conventions
- Each app owns its models, serializers, views, urls and tests.
- Views filter querysets by the authenticated user; never trust ids sent by the client.
- Write tests for every endpoint, especially permissions (user A must not see user B's data).
- Secrets live in `.env` (never committed). Keep `.env.example` with names only.
- After finishing a task, update `README.md` (what the project is) and `CHANGELOG.md` (dated log).
- Commit messages: short, English, imperative (for example `Add client endpoints`).
