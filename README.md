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

Public endpoints (no auth required). List responses are paginated
(`count`, `next`, `previous`, `results`; 10 per page).

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/profiles/` | List published profiles (filters: `?city=`, `?specialty=`) |
| GET | `/api/profiles/{slug}/` | Profile detail |
| GET | `/api/packages/` | List packages (filter: `?profile={slug}`) |
| GET | `/api/packages/{id}/` | Package detail |
| GET | `/api/portfolio-photos/` | List portfolio photos |
| GET | `/api/portfolio-photos/{id}/` | Photo detail |

Photographer endpoints (JWT + `role=photographer`): full CRUD on `/api/packages/` and
`/api/portfolio-photos/` for their own catalog. Also `/api/clients/` and `/api/shoots/`.

## Bookings (current)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/bookings/` | Customer creates a booking request (`package`, `date`, `message`) |
| GET | `/api/bookings/` | Customer: own requests / Photographer: incoming requests |
| POST | `/api/bookings/{id}/accept/` | Photographer accepts (pending only): creates the `Client` (reused) and a `Shoot` (`booked`); 400 if a shoot already exists that day |
| POST | `/api/bookings/{id}/reject/` | Photographer rejects (pending only) |

## Galleries (current)

Private: only the photographer of the shoot and that shoot's customer can access.

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/galleries/` | Photographer: own galleries / Customer: own galleries |
| POST | `/api/galleries/` | Photographer creates a gallery for one of their shoots (unique per shoot) |
| GET | `/api/photos/` | Same access rules as galleries |
| POST | `/api/photos/` | Photographer adds a photo to their own gallery |

## Run locally

```bash
python manage.py migrate
python manage.py runserver
```