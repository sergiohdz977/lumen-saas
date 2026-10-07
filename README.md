# lumen

A SaaS platform for photographers to manage clients,
shoots, and private galleries.

## Status

- In development

## Auth (current)

Roles are chosen at registration: `photographer` or `customer` (default).

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/auth/register/` | Create a user (`username`, `email`, `password`, optional `role`) |
| POST | `/api/auth/login/` | Obtain JWT (`access` / `refresh`) |
| POST | `/api/auth/token/refresh/` | Refresh the access token |

## Marketplace (current)

Public endpoints (no auth required):

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/profiles/` | List published photographer profiles |
| GET | `/api/profiles/{slug}/` | Profile detail |
| GET | `/api/packages/` | List packages (filter: `?profile={slug}`) |
| GET | `/api/packages/{id}/` | Package detail |
| GET | `/api/portfolio-photos/` | List portfolio photos |
| GET | `/api/portfolio-photos/{id}/` | Photo detail |

Photographer endpoints (JWT + `role=photographer`): full CRUD on `/api/packages/` and
`/api/portfolio-photos/` for their own catalog. Also `/api/clients/` and `/api/shoots/`.

## Run locally

```bash
python manage.py migrate
python manage.py runserver
```