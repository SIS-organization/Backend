# ProiectIP-Echipa2_Campus-Sports-Booking-Backend

Backend pentru rezervarea facilităților sportive USV (FastAPI + PostgreSQL).
Cerința 3.6 (IP Laborator 6): aplicația de bază cu **operații CRUD pentru entitatea `Booking`**.

## Cerințe

- Python 3.10+
- PostgreSQL 16 + pgAdmin 4

## Pornire (Windows / PyCharm)

1. **Mediu virtual și pachete**
   ```
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements-dev.txt
   ```
2. **Baza de date** — în pgAdmin creează baza `db_campus_sports`, apoi în *Query Tool* rulează,
   pe rând, `database/schema.sql` și `database/seed.sql`.
3. **Configurare** — copiază `.env.example` ca `.env` și pune parola ta de PostgreSQL.
4. **Pornire server**
   ```
   uvicorn app.main:app --reload
   ```
   Documentația interactivă (Swagger UI): http://localhost:8000/docs

## Teste

Rulează pe un PostgreSQL real, într-o bază separată. Creează în pgAdmin baza goală
`db_campus_sports_test` (schema și datele se creează automat din `database/*.sql`), apoi:

```
pytest
```

Verificarea stilului (PEP 8): `ruff check .` și `ruff format --check .`

## API (prefix `/v1`)

Până la autentificarea JWT (Epic 3), utilizatorul este identificat prin antetul
`X-User-Id` (id din `users`; în datele de test: 1 Andrei, 2 Daria, 3 Elena,
4 Administrator, 5 Vlad).

| Metodă | Cale | Descriere |
|---|---|---|
| GET | `/health` | Starea aplicației și a bazei de date |
| GET | `/facilities` | Lista facilităților |
| POST | `/bookings` | Creează rezervare (201) |
| GET | `/bookings?scope=upcoming\|history\|all&page=1&pageSize=20` | Rezervările mele |
| GET | `/bookings/{id}` | Detalii rezervare |
| PATCH | `/bookings/{id}` | Mută rezervarea în alt interval |
| POST | `/bookings/{id}/cancel` | Anulează rezervarea (rămâne în istoric) |

Exemplu de creare:

```json
POST /v1/bookings        (antet: X-User-Id: 1)
{ "facilityId": 3, "startTime": "2030-01-08T10:00:00+02:00", "endTime": "2030-01-08T11:00:00+02:00" }
```

### Reguli de rezervare

- exact 60 de minute, începând la oră fixă, în programul 08:00–21:00;
- nu se rezervă în trecut;
- o facilitate acceptă maximum `capacity` rezervări simultane (Bazin = 4);
- intervalele blocate (curs, eveniment, mentenanță) nu pot fi rezervate;
- anularea / mutarea se face cu cel puțin 2 ore înainte.

### Erori

Format RFC 7807 (`application/problem+json`) cu câmpul `code`:

| Status | `code` |
|---|---|
| 400 | `VALIDATION_ERROR` |
| 401 | `UNAUTHORIZED` |
| 403 | `FORBIDDEN` |
| 404 | `NOT_FOUND` |
| 409 | `SLOT_ALREADY_BOOKED`, `USER_ALREADY_BOOKED`, `FACILITY_UNDER_MAINTENANCE`, `BLOCKED_BY_UNIVERSITY_ACTIVITY`, `INVALID_BOOKING_STATE` |
| 422 | `INVALID_TIME_RANGE`, `OUTSIDE_OPENING_HOURS`, `SLOT_IN_THE_PAST`, `CANCELLATION_WINDOW_EXPIRED`, `MODIFICATION_WINDOW_EXPIRED` |

## Structura

```
app/
  main.py            aplicația, CORS, tratarea erorilor
  core/              configurare, conexiune DB, erori, ore locale
  models/            tabelele (SQLAlchemy)
  schemas/           formatul JSON (Pydantic)
  repositories/      interogările SQL
  services/          regulile de business
  routers/           endpoint-urile HTTP
database/            schema.sql, seed.sql
tests/               teste pytest pe PostgreSQL
```

Fluxul unei cereri: **router → service → repository → model**.
