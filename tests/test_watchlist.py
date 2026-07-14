"""
tests/test_watchlist.py — CineLog

Tests for the watchlist service. Fixtures and structure follow
tests/test_collection.py.
"""

import pytest
from app import create_app, db
from models import User, Film, WatchlistEntry
from services.watchlist_service import (
    add_to_watchlist,
    remove_from_watchlist,
    get_watchlist,
    AlreadyInWatchlistError,
    NotInWatchlistError,
)
from services.collection_service import FilmNotFoundError


@pytest.fixture
def app():
    """Create an isolated test app with an in-memory database."""
    app = create_app(config={
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
    })
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def sample_user(app):
    """A user to use in tests."""
    with app.app_context():
        user = User(username="testuser", email="test@example.com")
        db.session.add(user)
        db.session.commit()
        return user.id


@pytest.fixture
def sample_film(app):
    """A film to use in tests."""
    with app.app_context():
        film = Film(title="Paddington 2", year=2017, genre="Comedy")
        db.session.add(film)
        db.session.commit()
        return film.id


# ── Nonexistent film ─────────────────────────────────────────────────────────

def test_add_to_watchlist_nonexistent_film_raises(app, sample_user):
    """
    Adding a film_id that doesn't exist in the database should raise
    FilmNotFoundError, not a database integrity error.
    """
    with app.app_context():
        fake_film_id = "00000000-0000-0000-0000-000000000000"

        with pytest.raises(FilmNotFoundError):
            add_to_watchlist(user_id=sample_user, film_id=fake_film_id)


# ── Remove ───────────────────────────────────────────────────────────────────

def test_remove_from_watchlist_removes_entry(app, sample_user, sample_film):
    """
    Removing a film that's on the watchlist should delete the entry.
    """
    with app.app_context():
        add_to_watchlist(user_id=sample_user, film_id=sample_film)

        removed = remove_from_watchlist(user_id=sample_user, film_id=sample_film)
        assert removed is True

        in_db = WatchlistEntry.query.filter_by(
            user_id=sample_user, film_id=sample_film
        ).first()
        assert in_db is None


def test_remove_from_watchlist_not_in_watchlist_raises(app, sample_user, sample_film):
    """
    Removing a film that isn't on the watchlist should raise
    NotInWatchlistError, not silently succeed.
    """
    with app.app_context():
        with pytest.raises(NotInWatchlistError):
            remove_from_watchlist(user_id=sample_user, film_id=sample_film)


# ── Visibility ───────────────────────────────────────────────────────────────

def test_add_to_watchlist_respects_public_flag(app, sample_user, sample_film):
    """
    Passing public=False should override the default and persist as private.
    """
    with app.app_context():
        entry = add_to_watchlist(user_id=sample_user, film_id=sample_film, public=False)

        assert entry.public is False

        in_db = WatchlistEntry.query.filter_by(
            user_id=sample_user, film_id=sample_film
        ).first()
        assert in_db.public is False


# ── Sort order ───────────────────────────────────────────────────────────────

def test_get_watchlist_returns_alphabetical_order(app, sample_user):
    """
    get_watchlist() should return films sorted alphabetically by title,
    regardless of the order they were added in.

    This exercises the Comment 5 design decision (see pr-response.md):
    unlike get_collection(), which sorts by date_added desc, the watchlist
    intentionally sorts alphabetically. Without this test, a future change
    could silently flip the sort order back to date-added and nothing
    would catch it.
    """
    with app.app_context():
        film_z = Film(title="Zodiac", year=2007, genre="Thriller")
        film_a = Film(title="Amelie", year=2001, genre="Romance")
        db.session.add_all([film_z, film_a])
        db.session.commit()

        # Add "Zodiac" first, "Amelie" second — the opposite of alphabetical
        # order — to confirm the sort isn't just reflecting insertion order.
        add_to_watchlist(user_id=sample_user, film_id=film_z.id)
        add_to_watchlist(user_id=sample_user, film_id=film_a.id)

        watchlist = get_watchlist(sample_user)
        titles = [f["title"] for f in watchlist]

        assert titles == ["Amelie", "Zodiac"]
