"""Clase comune pentru scheme."""

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class CamelModel(BaseModel):
    """JSON în camelCase (startTime), atribute Python în snake_case (start_time)."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
    )


class PageMeta(CamelModel):
    """Informații de paginare."""

    page: int
    page_size: int
    total_items: int
    total_pages: int
