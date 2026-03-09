from dataclasses import dataclass
from math import ceil

from fastapi import Response


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


def set_pagination_headers(response: Response, meta: PaginationMeta) -> None:
    response.headers["X-Total-Count"] = str(meta.total_count)
    response.headers["X-Page"] = str(meta.page)
    response.headers["X-Page-Size"] = str(meta.page_size)
    response.headers["X-Total-Pages"] = str(meta.total_pages)
