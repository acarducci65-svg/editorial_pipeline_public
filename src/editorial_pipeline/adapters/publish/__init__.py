"""Local publication adapters; all targets require prior Gate 2 validation."""

from .author_website import AuthorWebsitePublisher
from .base import PublishAdapter, PublishResult
from .dist_archive import DistArchivePublisher
from .static_site import StaticSitePublisher

__all__ = [
    "AuthorWebsitePublisher",
    "DistArchivePublisher",
    "PublishAdapter",
    "PublishResult",
    "StaticSitePublisher",
]
