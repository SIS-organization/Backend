"""Endpoint-uri pentru facilități."""

from fastapi import APIRouter

from app.routers.dependencies import DbSession
from app.schemas.facility import FacilityList
from app.services.facility_service import FacilityService

router = APIRouter(prefix="/facilities", tags=["Facilities"])


@router.get("", response_model=FacilityList, summary="Lista facilităților")
def list_facilities(db: DbSession) -> FacilityList:
    facilities = FacilityService(db).list_all()
    return FacilityList(items=facilities)
