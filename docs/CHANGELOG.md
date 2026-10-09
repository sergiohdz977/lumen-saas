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
- Added marketplace integration tests (full journey: register → profile → package → book →
  accept → shoot states; rejected-booking retry; package `profile` spoof regression)
  — Phase 2 complete (110 passing total)
- Next: Phase 3, `galleries`: `Gallery` and `Photo` models, private access rules