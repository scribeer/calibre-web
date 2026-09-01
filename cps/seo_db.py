# -*- coding: utf-8 -*-

from datetime import datetime, timezone
from functools import lru_cache

from sqlalchemy import Boolean, Column, DateTime, Integer, String, UniqueConstraint, text
from sqlalchemy.exc import IntegrityError
try:
    from sqlalchemy.orm import declarative_base
except ImportError:
    from sqlalchemy.ext.declarative import declarative_base

from . import ub
from .seo_urls import book_slug_parts, primary_author


Base = declarative_base()


class SeoBookRoute(Base):
    __tablename__ = "aubooks_seo_book_route"
    __table_args__ = (
        UniqueConstraint("library_uuid", "author_slug", "book_slug", name="uq_aubooks_seo_route"),
    )

    id = Column(Integer, primary_key=True)
    library_uuid = Column(String(36), nullable=False)
    book_id = Column(Integer, nullable=False)
    author_slug = Column(String(96), nullable=False)
    book_slug = Column(String(112), nullable=False)
    is_canonical = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))


def init_db(session=None):
    session = session or ub.session
    engine = session.bind
    Base.metadata.create_all(engine)
    session.execute(text(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_aubooks_seo_canonical_book "
        "ON aubooks_seo_book_route (library_uuid, book_id) WHERE is_canonical = 1"
    ))
    session.execute(text(
        "CREATE INDEX IF NOT EXISTS ix_aubooks_seo_book "
        "ON aubooks_seo_book_route (library_uuid, book_id)"
    ))
    session.execute(text(
        "CREATE INDEX IF NOT EXISTS ix_aubooks_seo_sitemap "
        "ON aubooks_seo_book_route (library_uuid, is_canonical, book_id)"
    ))
    session.commit()


def get_canonical(library_uuid, book_id, session=None):
    session = session or ub.session
    return session.query(SeoBookRoute).filter(
        SeoBookRoute.library_uuid == library_uuid,
        SeoBookRoute.book_id == book_id,
        SeoBookRoute.is_canonical == True,  # noqa: E712
    ).one_or_none()


def resolve_route(library_uuid, author_slug, book_slug, session=None):
    session = session or ub.session
    return session.query(SeoBookRoute).filter(
        SeoBookRoute.library_uuid == library_uuid,
        SeoBookRoute.author_slug == author_slug,
        SeoBookRoute.book_slug == book_slug,
    ).one_or_none()


def _language_for_book(book):
    codes = [getattr(language, "lang_code", "") for language in getattr(book, "languages", [])]
    if "ukr" in codes:
        return "ukr"
    if "rus" in codes:
        return "rus"
    return codes[0] if codes else None


def _slug_parts(book):
    author = primary_author(book.authors, book.author_sort)
    author_name = author.name if author is not None else "Unknown author"
    return book_slug_parts(author_name, book.title, _language_for_book(book))


def ensure_canonical(library_uuid, book, session=None):
    session = session or ub.session
    existing = get_canonical(library_uuid, book.id, session)
    if existing is not None:
        return existing

    author_slug, base_book_slug = _slug_parts(book)
    suffix = 1

    while True:
        book_slug = base_book_slug if suffix == 1 else "{}-{}".format(base_book_slug, suffix)
        route = SeoBookRoute(
            library_uuid=library_uuid,
            book_id=book.id,
            author_slug=author_slug,
            book_slug=book_slug,
            is_canonical=True,
        )
        session.add(route)
        try:
            session.commit()
            clear_route_cache()
            return route
        except IntegrityError:
            session.rollback()
            existing = get_canonical(library_uuid, book.id, session)
            if existing is not None:
                return existing
            suffix += 1


def replace_canonical(library_uuid, book, session=None):
    session = session or ub.session
    current = get_canonical(library_uuid, book.id, session)
    if current is None:
        return ensure_canonical(library_uuid, book, session)

    author_slug, base_book_slug = _slug_parts(book)
    if (current.author_slug, current.book_slug) == (author_slug, base_book_slug):
        return current

    suffix = 1
    while True:
        book_slug = base_book_slug if suffix == 1 else "{}-{}".format(base_book_slug, suffix)
        occupied = resolve_route(library_uuid, author_slug, book_slug, session)
        if occupied is not None:
            if occupied.book_id == book.id:
                current.is_canonical = False
                session.flush()
                occupied.is_canonical = True
                session.commit()
                clear_route_cache()
                return occupied
            suffix += 1
            continue
        route = SeoBookRoute(
            library_uuid=library_uuid,
            book_id=book.id,
            author_slug=author_slug,
            book_slug=book_slug,
            is_canonical=True,
        )
        current.is_canonical = False
        session.add(route)
        try:
            session.commit()
            clear_route_cache()
            return route
        except IntegrityError:
            session.rollback()
            current = get_canonical(library_uuid, book.id, session)
            suffix += 1


@lru_cache(maxsize=131072)
def cached_canonical_parts(library_uuid, book_id):
    route = get_canonical(library_uuid, book_id)
    if route is None:
        return None
    return route.author_slug, route.book_slug


def clear_route_cache():
    cached_canonical_parts.cache_clear()
