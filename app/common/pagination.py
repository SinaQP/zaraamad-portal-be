from dataclasses import dataclass
from math import ceil
from typing import Generic, TypeVar

from fastapi import Query, Response
from pydantic import Field

from app.common.dtos import MongoDTO

DEFAULT_PAGE = 1
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100

T = TypeVar("T")


class PaginatedResponse(MongoDTO, Generic[T]):
    items: list[T] = Field(..., description="List of items for the current page.")
    total_page: int = Field(..., description="Total number of pages.", examples=[3])


@dataclass(frozen=True)
class PaginationParams:
    page: int
    page_size: int

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


@dataclass(frozen=True)
class PaginationMeta:
    total_count: int
    page: int
    page_size: int

    @property
    def total_pages(self) -> int:
        if self.total_count == 0:
            return 0
        return ceil(self.total_count / self.page_size)


def get_pagination_params(
    page: int = Query(default=DEFAULT_PAGE, ge=1, description="Page number (1-based)."),
    page_size: int = Query(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE, description="Page size."),
) -> PaginationParams:
    return PaginationParams(page=page, page_size=page_size)


def set_pagination_headers(response: Response, meta: PaginationMeta) -> None:
    response.headers["X-Total-Count"] = str(meta.total_count)
    response.headers["X-Page"] = str(meta.page)
    response.headers["X-Page-Size"] = str(meta.page_size)
    response.headers["X-Total-Pages"] = str(meta.total_pages)
