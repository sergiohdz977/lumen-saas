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
| GET | `/api/galleries/` | Photographer: own galleries / Customer: own galleries (filter: `?shoot=`) |
| POST | `/api/galleries/` | Photographer creates a gallery for one of their shoots (unique per shoot) |
| GET | `/api/photos/` | Same access rules as galleries (filter: `?gallery=`) |
| POST | `/api/photos/` | Photographer adds a photo: `multipart/form-data` with `gallery`, `image` (file) and optional `caption`. The response includes `thumbnail` (empty until the Celery worker generates it) |
| POST | `/api/photos/{id}/download/` | Register a download: `{"version": "light"}` (HD preview) or `{"version": "original"}` (default). Separate counters per version |
| POST | `/api/favorites/` | Customer favorites a photo of their own gallery (`{"photo": id}`) |
| GET | `/api/favorites/` | Customer: their favorites / Photographer: client favorites on their own photos (with `customer_username` and thumbnail). Filter: `?photo=` |
| DELETE | `/api/favorites/{id}/` | Customer removes a favorite |
| POST | `/api/galleries/{id}/share-link/` | Photographer generates a signed share link for a customer (valid 7 days) |
| GET | `/api/gallery-view/{token}/` | Public: open gallery + photos with the share link, no login required |

## Reviews (current)

Customers rate photographers they have worked with (1-5 + optional comment).

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/reviews/` | Customer reviews a photographer: one per customer+photographer, only for photographers with a linked Client record |
| GET | `/api/reviews/` | Customer: reviews they wrote / Photographer: reviews received. Filter: `?photographer=` |
| PATCH | `/api/reviews/{id}/` | Customer edits their own review |
| DELETE | `/api/reviews/{id}/` | Customer deletes their own review |

## Notifications (current)

Real-time (WebSocket) + history (REST). Needs Redis/Memurai running for live
pushes; the rows are always saved even without it.

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/notifications/` | The logged-in user's own notifications (paginated) |
| POST | `/api/notifications/{id}/read/` | Mark one as read |
| POST | `/api/notifications/read-all/` | Mark all as read |
| WS | `/ws/notifications/?token={ACCESS}` | Open line; server pushes new notifications as they happen (session login also works) |

Events that create a notification: booking accepted (to the customer),
gallery created (to the customer), new review (to the photographer).

## Run locally

```bash
python manage.py migrate
python manage.py runserver
```

Background tasks (thumbnails and emails) need Redis/Memurai running and a Celery worker
(in a second terminal; Windows requires the `solo` pool):

```bash
venv\Scripts\celery.exe -A config worker --pool=solo -l info
```

Emails are printed to the worker terminal in development (console backend):
booking accept and gallery delivery send a message with a private share link.