"""Rolul unui utilizator, recunoscut din identitatea instituțională.

Aceeași logică se aplică furnizorului simulat și celui real:

1. Afilierea declarată de SSO are prioritate: personal didactic / angajat → cadru
   didactic (`professor`), student → `student`. Dacă are ambele, câștigă rolul
   de cadru didactic.
2. Dacă SSO nu trimite afilieri, se folosește domeniul e-mailului
   instituțional: `@student.usv.ro` → student, `@usv.ro` → cadru didactic.
3. Altfel contul NU este eligibil (None).

Rolul `administrator` nu se atribuie niciodată automat de aici (ar fi o
escaladare de privilegii): îl primește doar un cont deja marcat astfel în baza
de date de către echipă.
"""

from app.models.enums import UserRole
from app.services.sso.provider import SsoIdentity

STUDENT_DOMAIN = "student.usv.ro"
STAFF_DOMAIN = "usv.ro"
STAFF_AFFILIATIONS = {"faculty", "employee", "staff"}


def role_for_identity(identity: SsoIdentity) -> UserRole | None:
    affiliations = {a.strip().lower() for a in identity.affiliations}
    if affiliations & STAFF_AFFILIATIONS:
        return UserRole.PROFESSOR
    if "student" in affiliations:
        return UserRole.STUDENT

    domain = identity.email.rpartition("@")[2].strip().lower()
    if domain == STUDENT_DOMAIN:
        return UserRole.STUDENT
    if domain == STAFF_DOMAIN:
        return UserRole.PROFESSOR
    return None
