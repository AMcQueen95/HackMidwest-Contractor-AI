from backend.app.datasets import DatasetStore


def test_store_bounds_sessions_and_expires_them(books, monkeypatch):
    now = [100.0]
    monkeypatch.setattr("backend.app.datasets.time.monotonic", lambda: now[0])
    store = DatasetStore(books, max_sessions=1, ttl_seconds=10)
    first, _ = store.replace(books, None)
    second, second_dataset = store.replace(books, None)
    assert store.get(first).is_sample is True
    assert store.get(second) == second_dataset
    now[0] += 11
    assert store.get(second).is_sample is True


def test_replacement_preserves_session_and_changes_revision(books):
    store = DatasetStore(books)
    token, first = store.replace(books, "unknown-cookie")
    assert token != "unknown-cookie"
    second_token, second = store.replace(books, token)
    assert second_token == token and first.revision != second.revision
