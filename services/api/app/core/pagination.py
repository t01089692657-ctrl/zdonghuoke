"""通用分页。所有列表接口统一返回 Page[T]，前端一套渲染逻辑。"""
from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class PageParams(BaseModel):
    page: int = 1
    size: int = 20

    @property
    def offset(self) -> int:
        return (max(self.page, 1) - 1) * self.size

    @property
    def limit(self) -> int:
        return min(max(self.size, 1), 200)


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    size: int

    @classmethod
    def of(cls, items: list[T], total: int, params: PageParams) -> Page[T]:
        return cls(items=items, total=total, page=params.page, size=params.size)
