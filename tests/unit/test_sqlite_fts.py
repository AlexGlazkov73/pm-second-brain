from pathlib import Path

from pm_second_brain.mcp_servers.sqlite_fts import FtsStore


def test_init_creates_schema(tmp_path: Path) -> None:
    db = tmp_path / "sessions.db"
    store = FtsStore(db)
    store.init_schema()
    assert db.exists()
    # Re-opening must not error
    store2 = FtsStore(db)
    store2.init_schema()


def test_index_and_search(tmp_path: Path) -> None:
    store = FtsStore(tmp_path / "sessions.db")
    store.init_schema()
    store.index(
        "decisions/2026-05-17-pricing.md",
        "Tiered pricing",
        "We chose tiered pricing for Q2 because of the SMB segment.",
    )
    store.index(
        "decisions/2026-04-10-rollout.md",
        "Rollout plan",
        "Phased rollout starting in EU.",
    )
    rows = store.search("pricing Q2")
    assert len(rows) >= 1
    assert rows[0]["path"] == "decisions/2026-05-17-pricing.md"
    assert "snippet" in rows[0]
    assert "rank" in rows[0]


def test_index_replaces_on_same_path(tmp_path: Path) -> None:
    store = FtsStore(tmp_path / "sessions.db")
    store.init_schema()
    store.index("a.md", "T1", "alpha")
    store.index("a.md", "T1", "beta")
    assert store.search("alpha") == []
    rows = store.search("beta")
    assert len(rows) == 1


def test_search_respects_limit(tmp_path: Path) -> None:
    store = FtsStore(tmp_path / "sessions.db")
    store.init_schema()
    for i in range(20):
        store.index(f"n{i}.md", f"T{i}", "pricing")
    rows = store.search("pricing", limit=5)
    assert len(rows) == 5


def test_unicode_russian(tmp_path: Path) -> None:
    store = FtsStore(tmp_path / "sessions.db")
    store.init_schema()
    store.index("ru.md", "Цена", "Мы выбрали тарифную модель")
    rows = store.search("тарифную")
    assert len(rows) == 1


def test_stats(tmp_path: Path) -> None:
    store = FtsStore(tmp_path / "sessions.db")
    store.init_schema()
    store.index("a.md", "T", "x")
    store.index("b.md", "T", "y")
    st = store.stats()
    assert st["note_count"] == 2
