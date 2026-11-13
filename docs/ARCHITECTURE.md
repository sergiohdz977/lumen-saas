# Lumen — Architecture & Operations

Lumen is a photography marketplace and client workspace. The application keeps the product deliberately small at the edge: Django serves the API and the static web client, while PostgreSQL, Redis and the selected media provider handle persistence, asynchronous work and photo storage.

## Product boundaries

- **Marketplace:** public photographer profiles, specialties, packages, portfolio previews and reviews.
- **Bookings:** customer requests, photographer approval, shoot lifecycle and cancellation rules.
- **Galleries:** private photo delivery, signed share links, favorites and download tracking.
- **Payments:** Stripe Connect deposits and subscriptions, with a server-controlled demo mode for local demos.
- **Notifications:** durable REST history plus WebSocket delivery through Django Channels.

## Request flow

1. The browser loads a page from `frontend/`.
2. The page calls the REST API under `/api/` using a short-lived JWT access token.
3. Django REST Framework applies role and ownership permissions before serializers expose data.
4. Celery handles photo derivatives and email work outside the request cycle.
5. Channels publishes notification events through Redis when a live connection is available.

## Code map

- `config/` — settings, URL routing, ASGI and Celery configuration.
- `users/` — custom user model, roles, registration, JWT-facing endpoints and account updates.
- `profiles/` — photographer profiles, packages, portfolio collections and seed data.
- `bookings/`, `shoots/`, `clients/` — booking rules and the studio-side client workflow.
- `galleries/` — gallery access rules, storage, uploads and downloads.
- `payments/` — Stripe integration, demo payments and payment configuration.
- `notifications/` — notification persistence, REST endpoints and WebSocket consumers.
- `frontend/` — no-build HTML, CSS and JavaScript client.
- `docs/` — deployment notes, API schema and project documentation.

## Local setup

```bash
python -m venv .venv
source .venv/bin/activate                 # Windows: .venv\\Scripts\\activate
python -m pip install -r requirements.txt
cp .env.example .env                      # Windows: copy .env.example .env
python manage.py migrate
python manage.py seed_demo
python manage.py runserver
```

The default development database is SQLite. Redis is only required for live notifications and background Celery work; the test suite substitutes in-memory services and temporary media storage.

## Quality gates

Run these commands before opening a pull request:

```bash
python manage.py check
python manage.py test --noinput
for file in frontend/js/*.js; do node --check "$file"; done
```

Production deployments should set `DJANGO_DEBUG=0`, a real `DJANGO_SECRET_KEY`, explicit allowed hosts and trusted origins, a production database, Redis and the required Stripe or Cloudinary credentials. The deployment checklist lives in [`DEPLOY.md`](DEPLOY.md).

## Design direction

The interface uses an editorial studio language: cool slate surfaces, a deep teal action color, generous spacing and quiet borders. The visual system is intentionally free of vendor badges, generated-art labels or third-party watermarks so the product identity remains Lumen's.
