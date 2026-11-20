# ProiectIP-Echipa2_Campus-Sports-Booking-Backend

Backend pentru rezervarea facilităților sportive USV (FastAPI + PostgreSQL).
Aplicația de bază cu **operații CRUD pentru entitatea `Booking`**.

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
   Dacă ai deja baza creată și vrei să păstrezi datele, rulează doar scripturile din
   `database/migrations/` (de exemplu `2026-11-19_booking_cancellation.sql`, care adaugă
   motivul și autorul anulării).
3. **Configurare** — copiază `.env.example` ca `.env`, pune parola ta de PostgreSQL și
   o cheie secretă pentru JWT (**obligatorie**, minim 32 de caractere; fără ea aplicația nu pornește):
   ```
   python -c "import secrets; print(secrets.token_urlsafe(48))"
   ```
   Rezultatul îl pui în `.env` la `JWT_SECRET=`. Cheia nu se urcă pe GitHub și e diferită pe fiecare mediu.
   După un `git pull`, rulează `pip install -r requirements-dev.txt` (a apărut PyJWT).
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

Toate endpoint-urile cer antetul `Authorization: Bearer <JWT>`, **în afară de** `/health` și `/auth/sso/*`
(publice). Fără token valid răspunsul este `401`; cu token valid, dar fără rolul potrivit, `403`
(vezi „Protejarea endpoint-urilor după rol”).

**Cum obții un JWT ca să testezi:** deschide `http://localhost:8000/v1/auth/sso/login`, alege un cont
(student, cadru didactic sau administrator) și copiază `accessToken` din JSON. În Swagger UI
(`/docs`) apasă **Authorize** și lipește token-ul. Token-ul expiră în 60 de minute.

| Metodă | Cale | Descriere |
|---|---|---|
| GET | `/health` | Starea aplicației și a bazei de date (public) |
| GET | `/auth/sso/login?redirectTo=/facilitati` | Pornește autentificarea SSO: redirect 302 către furnizorul SSO (public) |
| GET | `/auth/sso/callback?code=&state=` | Încheie autentificarea: utilizatorul local cu rolul corect + JWT (public) |
| GET | `/facilities?q=&sport=&amenities=&date=&includeUnavailable=&page=&pageSize=` | Catalogul de facilități, cu filtre, stare și „următorul interval liber" |
| GET | `/facilities/{id}/availability?from=YYYY-MM-DD&to=YYYY-MM-DD` | Calendarul pe zile și ore (`free`, `booked`, `university_course`, `university_event`, `maintenance`, `past`, `closed`); implicit 7 zile de azi, maximum 14 |
| POST | `/bookings` | Creează rezervare (201, antet `Location`) |
| GET | `/bookings?scope=upcoming\|history\|all&status=&facilityId=&page=1&pageSize=20` | Rezervările mele |
| GET | `/bookings/{id}` | Detalii rezervare |
| PATCH | `/bookings/{id}` | Mută rezervarea în alt interval (nu e în Swagger) |
| POST | `/bookings/{id}/cancel` | Anulează rezervarea (rămâne în istoric); răspuns `{booking, quotaRestored, waitlistNotified}` |
| GET | `/users/me` | Profilul utilizatorului curent |
| PATCH | `/users/me` | Actualizează `firstName` și/sau `lastName` (rolul și e-mailul nu se schimbă) |
| orice | `/admin/*` | Doar administratori: `401` fără autentificare, `403` pentru ceilalți (încă fără endpoint-uri, vezi mai jos) |

Exemplu de creare:

```json
POST /v1/bookings        (antet: Authorization: Bearer <JWT>)
{ "facilityId": 3, "startTime": "2030-01-08T10:00:00+02:00", "endTime": "2030-01-08T11:00:00+02:00" }
```

### Autentificare cu SSO (KAN-19)

Fluxul este OpenID Connect, *Authorization Code + PKCE*, ca în Swagger:

1. `GET /auth/sso/login` generează un `state` semnat și `code_challenge` (PKCE) și redirecționează (302) la SSO.
2. SSO autentifică utilizatorul și îl trimite la `SSO_REDIRECT_URI` cu `code` și `state`.
3. `GET /auth/sso/callback` verifică `state`, schimbă `code` pe identitate (cu PKCE), creează sau actualizează
   utilizatorul local și întoarce `{accessToken, refreshToken, tokenType, expiresIn, user}`.

**SSO-ul real al universității nu este disponibil**, deci se folosește un furnizor **simulat** (`SSO_MODE=mock`, implicit),
cu același flux și aceeași logică de roluri. Încearcă-l: deschide în browser
`http://localhost:8000/v1/auth/sso/login`, alege un cont din lista „universității” și vei vedea JSON-ul cu `user.role` și
JWT-ul. Conturile simulate acoperă: student existent și student nou (contul se creează la prima autentificare),
cadru didactic, administrator, cont dezactivat (403) și cont fără afiliere USV (403). Furnizorul simulat este
pentru dezvoltare și demo, nu pentru producție; când universitatea oferă datele de conectare, se adaugă un
furnizor OIDC în `app/services/sso/` (restul codului rămâne neschimbat).

**Rolul** se recunoaște din identitatea instituțională (`app/services/sso/roles.py`): afilierea trimisă de SSO
(`faculty`/`employee`/`staff` → cadru didactic, `student` → student), iar dacă lipsește, domeniul e-mailului
(`@student.usv.ro` → student, `@usv.ro` → cadru didactic). Altfel contul nu este eligibil (403
`ACCOUNT_NOT_ELIGIBLE`). Rolul `administrator` nu se atribuie niciodată automat: îl păstrează doar conturile marcate
astfel în baza de date.

**JWT**: semnat HS256 cu `JWT_SECRET`; claim-uri `sub` (id utilizator), `role`, `exp` (+ `iat`, `token_use`);
valabilitate 60 de minute (`JWT_ACCESS_TTL_MINUTES`). Fiecare tip de token (acces, reînnoire, `state`, cod SSO) are o cheie
derivată proprie, deci nu pot fi folosite unul în locul altuia. `refreshToken` este emis, dar `/auth/refresh` și
`/auth/logout` nu sunt implementate încă.

Setări opționale în `.env`: `SSO_MODE`, `SSO_REDIRECT_URI` (implicit callback-ul backend-ului; pentru frontend,
ruta lui care apelează `/auth/sso/callback`), `JWT_ACCESS_TTL_MINUTES`, `JWT_REFRESH_TTL_DAYS`.

### Protejarea endpoint-urilor după rol (KAN-21)

Fiecare cerere trece prin `get_current_user` (`app/routers/dependencies.py`), care verifică JWT-ul:

| Situație | Răspuns |
|---|---|
| fără antet `Authorization`, schemă diferită de `Bearer`, token alterat, expirat, semnat cu altă cheie, de alt tip (de exemplu cel de reînnoire) sau al unui utilizator care nu mai există | `401` `UNAUTHENTICATED` (cu antetul `WWW-Authenticate: Bearer`) |
| token valid, dar rolul nu are voie | `403` `FORBIDDEN` |
| token valid și rol permis | cererea se execută |

* **Rolul se citește din baza de date**, nu din token. Un token care pretinde `administrator` nu dă drepturi
  unui student, iar un administrator retrogradat pierde accesul imediat, chiar dacă token-ul lui n-a expirat.
* **`/admin/*` este doar pentru administratori.** Garda (`require_admin`) este pusă pe routerul `/admin`
  (`app/routers/admin_router.py`), nu pe fiecare endpoint: orice endpoint de administrare adăugat acolo
  (Epic 9) este protejat automat. Până atunci, orice cale `/admin/...` răspunde `401` fără token, `403`
  unui ne-administrator (chiar și pe o cale care nu există, ca să nu aflăm ce există) și `404` unui administrator.
* **Alte reguli pe rol** se declară cu `Depends(require_roles(UserRole.PROFESSOR, UserRole.ADMINISTRATOR))`.
* **Endpoint-urile publice** sunt doar `/health`, `/auth/sso/login` și `/auth/sso/callback`. Un endpoint nou
  este protejat implicit (dacă declară `CurrentUser`); `tests/test_authorization.py` parcurge toate rutele
  din Swagger și pică dacă una nouă rămâne neprotejată din greșeală.
* Antetul provizoriu `X-User-Id` a fost **eliminat**: oricine ar fi putut pretinde că e administrator.

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
  core/              configurare, conexiune DB, erori, ore locale, JWT (security.py)
  models/            tabelele (SQLAlchemy)
  schemas/           formatul JSON (Pydantic)
  repositories/      interogările SQL
  services/          regulile de business (sso/: furnizori SSO, PKCE, roluri)
  routers/           endpoint-urile HTTP
database/            schema.sql, seed.sql, migrations/ (modificări pentru baze existente)
tests/               teste pytest pe PostgreSQL
```

Fluxul unei cereri: **router → service → repository → model**.

##

- Id-urile sunt numere întregi (în Swagger: UUID).
- Facilitatea are `type` și `capacity` (4 culoare la bazin); intervalele din calendar au `capacity` și `freeSpots`.
- `sports` și `amenities` sunt deduse din tipul facilității (`app/services/facility_catalog.py`).
- Statusurile rezervării sunt `confirmed`, `cancelled`, `completed`. Cota lunară (`/users/me/quota`), lista de așteptare și eliberarea anticipată nu sunt implementate încă, deci `quotaRestored` este mereu `false`, `waitlistAvailable` este `false`, iar `usesIncludedQuota` nu este returnat. QR-ul și plățile au fost scoase din proiect (la fel în Swagger-ul actualizat).
- Anularea salvează motivul (`cancelReason`, max. 300 de caractere, opțional) și autorul (`cancelledBy`: `user` sau `administrator`) în coloanele `cancel_reason` și `cancelled_by` din `bookings`. `canReleaseEarly`, `replacedBookingId` și `quotaRefunded` nu sunt returnate.
- `PATCH /users/me` modifică numele (nu există coloană pentru `mobileNumber`); `GET /users/me` nu returnează `faculty`, `department`, `campus`, `mobileNumber`.
- Autentificare: sunt implementate doar `/auth/sso/login` și `/auth/sso/callback` (cu SSO simulat). Lipsesc `/auth/refresh`, `/auth/logout` și login-ul extern (KAN-20). Răspunsul callback-ului are în plus `redirectTo` (ruta cerută la login).
