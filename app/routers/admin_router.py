"""Zona `/admin/*`: accesibilă DOAR administratorilor.

* fără autentificare → 401; autentificat dar fără rol de administrator → 403;
* garda (`require_admin`) este pusă pe ROUTER, nu pe fiecare endpoint, deci orice
  endpoint adăugat aici (Epic 9) este protejat automat, fără să se poată uita.

`fallback_router` prinde orice `/admin/...` încă neimplementat și trebuie
înregistrat ULTIMUL în `main.py`. Astfel garda se aplică pe tot prefixul:
un ne-administrator primește 403 chiar și pe o cale care nu există (nu aflăm
nimic despre ce există), iar un administrator primește 404.
"""

from fastapi import APIRouter, Depends, Request

from app.core.exceptions import NotFoundError
from app.routers.dependencies import require_admin

# Endpoint-urile de administrare se adaugă aici: `@router.get("/bookings")` etc.
router = APIRouter(
    prefix="/admin", tags=["Admin"], dependencies=[Depends(require_admin)]
)

fallback_router = APIRouter(
    prefix="/admin", dependencies=[Depends(require_admin)], include_in_schema=False
)

_METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE"]


@fallback_router.api_route("", methods=_METHODS)
@fallback_router.api_route("/{path:path}", methods=_METHODS)
def admin_not_found(request: Request) -> None:
    raise NotFoundError("Resursa de administrare nu există.")
