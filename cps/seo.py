# -*- coding: utf-8 -*-

import math
import os
import re
from html.parser import HTMLParser
from xml.sax.saxutils import escape as xml_escape

from flask import Blueprint, Response, abort, redirect, stream_with_context, url_for as flask_url_for
from flask_babel import get_locale

from . import calibre_db, config, db, isoLanguages, seo_db, ub
from .usermanagement import login_required_if_no_ano


seo = Blueprint("seo", __name__)
SITEMAP_PAGE_SIZE = 20000
METADATA_ENDPOINTS = {
    "author": "web.author_books",
    "series": "web.series_books",
    "category": "web.genre_books",
    "publisher": "web.publisher_books",
    "language": "web.language_books",
    "ratings": "web.rating_books",
}


class _TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_data(self, data):
        self.parts.append(data)


def _library_uuid():
    if config.config_calibre_uuid:
        return config.config_calibre_uuid
    library = calibre_db.session.query(db.Library_Id).first()
    return library.uuid if library else None


def external_url(endpoint, **values):
    path = flask_url_for(endpoint, _external=False, **values)
    public_url = os.getenv("AUBOOKS_PUBLIC_URL", "").rstrip("/")
    if public_url:
        return public_url + path
    return flask_url_for(endpoint, _external=True, **values)


def _plain_text(value):
    parser = _TextExtractor()
    parser.feed(value or "")
    return re.sub(r"\s+", " ", " ".join(parser.parts)).strip()


def _description(entry, author_names):
    if entry.comments and entry.comments[0].text:
        description = _plain_text(entry.comments[0].text)
    else:
        description = "{} — {}".format(entry.title, ", ".join(author_names))
    if len(description) <= 160:
        return description
    return description[:157].rsplit(" ", 1)[0].rstrip(" ,.;:-") + "..."


def _route_for_book(book_id, create=False):
    library_uuid = _library_uuid()
    if not library_uuid:
        return None
    route = seo_db.get_canonical(library_uuid, book_id)
    if route is None and create:
        book = calibre_db.get_book(book_id)
        if book is not None:
            session = ub.init_db_thread()
            try:
                seo_db.ensure_canonical(library_uuid, book, session)
            finally:
                session.close()
            route = seo_db.get_canonical(library_uuid, book_id)
    return route


def book_url(book_id, create=False, **values):
    library_uuid = _library_uuid()
    parts = seo_db.cached_canonical_parts(library_uuid, book_id) if library_uuid else None
    if parts is None and create:
        route = _route_for_book(book_id, create=True)
        parts = (route.author_slug, route.book_slug) if route is not None else None
    if parts is None:
        return flask_url_for("web.show_book", book_id=book_id, **values)
    return flask_url_for(
        "seo.book_detail",
        author_slug=parts[0],
        book_slug=parts[1],
        **values
    )


def aubooks_page_title(kind, label=None, author=None):
    if kind == "home":
        return "AU-Books — аудиокниги и электронные книги"
    if kind == "book":
        return "{} — {} | AU-Books".format(label, author)
    if kind == "author":
        return "{} — книги | AU-Books".format(label)
    if kind == "series":
        return "{} — книги серии | AU-Books".format(label)
    if kind == "search":
        return "Поиск: {} | AU-Books".format(label or "")
    return "{} — книги | AU-Books".format(label)


def _genre_details(entity_key):
    tag_ids = [int(value) for value in str(entity_key).split("+") if value.isdigit()]
    if not tag_ids:
        return None
    tags = calibre_db.session.query(db.Tags).filter(db.Tags.id.in_(tag_ids)).all()
    if not tags:
        return None

    from .aubooks_genres import genre_for_tag
    genre = genre_for_tag(tags[0])
    if genre["mapped"]:
        from .render_template import _get_aubooks_sidebar_genre_tree
        for group in _get_aubooks_sidebar_genre_tree():
            for candidate in group["genres"]:
                if candidate["code"] == genre["code"]:
                    ids = sorted(candidate["tag_ids"])
                    return "+".join(str(tag_id) for tag_id in ids), candidate["label"]
    return str(tags[0].id), genre["label"]


def metadata_details(entity_type, entity_key):
    if entity_type == "category":
        return _genre_details(entity_key)
    if entity_type == "language":
        language = calibre_db.session.query(db.Languages).filter(
            db.Languages.lang_code == str(entity_key)
        ).first()
        if language is None:
            return None
        label = isoLanguages.get_language_name(get_locale(), language.lang_code)
        return language.lang_code, label

    try:
        entity_id = int(entity_key)
    except (TypeError, ValueError):
        return None
    model = {
        "author": db.Authors,
        "series": db.Series,
        "publisher": db.Publishers,
        "ratings": db.Ratings,
    }.get(entity_type)
    if model is None:
        return None
    entity = calibre_db.session.query(model).filter(model.id == entity_id).first()
    if entity is None:
        return None
    if entity_type == "ratings":
        stars = int(entity.rating / 2)
        label = "{} {}".format(stars, "звезда" if stars == 1 else "звезды" if stars < 5 else "звезд")
    else:
        label = entity.name.replace("|", ",")
    return str(entity_id), label


def _metadata_route(entity_type, entity_key, create=False):
    library_uuid = _library_uuid()
    details = metadata_details(entity_type, entity_key)
    if not library_uuid or details is None:
        return None, None
    normalized_key, label = details
    slug = seo_db.cached_metadata_slug(library_uuid, entity_type, normalized_key)
    route = None
    if slug is None and create:
        session = ub.init_db_thread()
        try:
            seo_db.ensure_metadata_route(
                library_uuid, entity_type, normalized_key, label, session
            )
        finally:
            session.close()
        route = seo_db.get_metadata_route(library_uuid, entity_type, normalized_key)
    elif slug is not None:
        route = seo_db.get_metadata_route(library_uuid, entity_type, normalized_key)
    return route, label


def metadata_url(entity_type, entity_key, create=False, **values):
    endpoint = METADATA_ENDPOINTS.get(entity_type)
    route, __ = _metadata_route(entity_type, entity_key, create=create)
    if endpoint is None or route is None:
        return None
    return flask_url_for(endpoint, slug=route.slug, **values)


def resolve_metadata(entity_type, slug):
    library_uuid = _library_uuid()
    if not library_uuid:
        return None
    route = seo_db.resolve_metadata_route(library_uuid, entity_type, slug)
    if route is None:
        return None
    details = metadata_details(entity_type, route.entity_key)
    if details is None:
        return None
    entity_key, label = details
    return route, entity_key, label


def metadata_context(entity_type, route, label):
    endpoint = METADATA_ENDPOINTS[entity_type]
    return {
        "canonical_url": external_url(endpoint, slug=route.slug),
        "seo_title": aubooks_page_title(entity_type, label=label),
    }


def template_url_for(endpoint, **values):
    if endpoint == "web.show_book" and "book_id" in values:
        book_id = values.pop("book_id")
        return book_url(book_id, **values)
    if endpoint == "web.books_list" and values.get("sort_param") == "stored":
        entity_type = values.get("data")
        if entity_type in METADATA_ENDPOINTS and "book_id" in values:
            metadata_values = dict(values)
            entity_key = metadata_values.pop("book_id")
            metadata_values.pop("data", None)
            metadata_values.pop("sort_param", None)
            friendly_url = metadata_url(entity_type, entity_key, create=True, **metadata_values)
            if friendly_url is not None:
                return friendly_url
    return flask_url_for(endpoint, **values)


@seo.app_context_processor
def seo_url_helpers():
    return {"url_for": template_url_for}


def detail_context(entry, route):
    author_names = [author.name.replace("|", ",") for author in entry.ordered_authors]
    canonical_url = external_url(
        "seo.book_detail",
        author_slug=route.author_slug,
        book_slug=route.book_slug,
    )
    description = _description(entry, author_names)
    structured_data = {
        "@context": "https://schema.org",
        "@type": "Book",
        "name": entry.title,
        "author": [{"@type": "Person", "name": name} for name in author_names],
        "description": description,
        "url": canonical_url,
    }
    languages = [language.lang_code for language in entry.languages if language.lang_code]
    if languages:
        structured_data["inLanguage"] = languages[0] if len(languages) == 1 else languages
    if entry.has_cover:
        structured_data["image"] = external_url(
            "web.get_cover", book_id=entry.id, resolution="og"
        )
    isbn = next((identifier.val for identifier in entry.identifiers if identifier.type.lower() == "isbn"), None)
    if isbn:
        structured_data["isbn"] = isbn
    author_label = ", ".join(author_names)
    return {
        "canonical_url": canonical_url,
        "seo_description": description,
        "seo_title": aubooks_page_title("book", label=entry.title, author=author_label),
        "seo_image": structured_data.get("image"),
        "seo_json_ld": structured_data,
    }


@seo.route("/books/<string:author_slug>/<string:book_slug>")
@login_required_if_no_ano
def book_detail(author_slug, book_slug):
    library_uuid = _library_uuid()
    if not library_uuid:
        abort(404)
    route = seo_db.resolve_route(library_uuid, author_slug, book_slug)
    if route is None:
        abort(404)
    canonical = seo_db.get_canonical(library_uuid, route.book_id)
    if canonical is None:
        abort(404)
    if calibre_db.get_filtered_book(route.book_id, allow_show_archived=True) is None:
        abort(404)
    if not route.is_canonical:
        return redirect(flask_url_for(
            "seo.book_detail", author_slug=canonical.author_slug, book_slug=canonical.book_slug
        ), code=301)

    from .web import render_book_detail
    return render_book_detail(route.book_id, canonical)


@seo.route("/sitemap.xml")
def sitemap_index():
    library_uuid = _library_uuid()
    if not library_uuid or not config.config_anonbrowse:
        abort(404)
    guest = ub.session.query(ub.User).filter(ub.User.name == "Guest").one()
    count = calibre_db.session.query(db.Books.id).filter(
        calibre_db.common_filters(allow_show_archived=True, user=guest)
    ).count()
    pages = int(math.ceil(count / float(SITEMAP_PAGE_SIZE)))
    items = [
        "  <sitemap><loc>{}</loc></sitemap>".format(xml_escape(external_url(
            "seo.book_sitemap", page=page
        )))
        for page in range(1, pages + 1)
    ]
    body = "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n" \
           "<sitemapindex xmlns=\"http://www.sitemaps.org/schemas/sitemap/0.9\">\n{}\n</sitemapindex>\n".format(
               "\n".join(items)
           )
    response = Response(body, mimetype="application/xml")
    response.headers["Cache-Control"] = "public, max-age=3600"
    return response


@seo.route("/sitemaps/books-<int:page>.xml")
def book_sitemap(page):
    library_uuid = _library_uuid()
    if not library_uuid or not config.config_anonbrowse or page < 1:
        abort(404)
    guest = ub.session.query(ub.User).filter(ub.User.name == "Guest").one()
    visible_books = calibre_db.session.query(db.Books.id, db.Books.last_modified).filter(
        calibre_db.common_filters(allow_show_archived=True, user=guest)
    ).order_by(db.Books.id).offset((page - 1) * SITEMAP_PAGE_SIZE).limit(SITEMAP_PAGE_SIZE).all()
    if not visible_books:
        abort(404)

    route_by_book = {}
    book_ids = [book_id for book_id, _ in visible_books]
    for offset in range(0, len(book_ids), 500):
        routes = ub.session.query(seo_db.SeoBookRoute).filter(
            seo_db.SeoBookRoute.library_uuid == library_uuid,
            seo_db.SeoBookRoute.is_canonical == True,  # noqa: E712
            seo_db.SeoBookRoute.book_id.in_(book_ids[offset:offset + 500]),
        ).all()
        route_by_book.update((route.book_id, route) for route in routes)

    def generate():
        yield "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
        yield "<urlset xmlns=\"http://www.sitemaps.org/schemas/sitemap/0.9\">\n"
        for book_id, last_modified in visible_books:
            route = route_by_book.get(book_id)
            if route is None:
                continue
            location = external_url(
                "seo.book_detail",
                author_slug=route.author_slug,
                book_slug=route.book_slug,
            )
            yield "  <url><loc>{}</loc><lastmod>{}</lastmod></url>\n".format(
                xml_escape(location), last_modified.date().isoformat()
            )
        yield "</urlset>\n"

    response = Response(stream_with_context(generate()), mimetype="application/xml")
    response.headers["Cache-Control"] = "public, max-age=3600"
    return response
