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
- Next: Phase 2, `profiles` module (PhotographerProfile with slug, public read-only endpoints)