from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ImageHit:
    query: str
    image_url: str
    product_url: str = ""
    mouser_part_number: str = ""
    manufacturer_part_number: str = ""
    manufacturer: str = ""
    description: str = ""


@dataclass
class SearchResult:
    query: str
    hits: list[ImageHit] = field(default_factory=list)
    error: str = ""
    raw_cache_path: str = ""
    search_mode: str = ""
