from app.analysis.intake import make_competitor, resolve_intake


def test_duplicate_competitor_is_flagged_and_skipped() -> None:
    target = make_competitor("Notero", "notero.com", "AI-native note-taking app", is_target=True)
    proposed = [
        make_competitor("Notion", "notion.so", "All-in-one workspace"),
        make_competitor("notion.so", None, "duplicate entry by domain-as-name"),
        make_competitor("Coda", "coda.io", "Docs that work like apps"),
        make_competitor("Airtable", "airtable.com", "Spreadsheet-database hybrid"),
        make_competitor("Slab", "slab.com", "Team knowledge base"),
    ]

    _, resolved, meets_minimum = resolve_intake(target, proposed, min_competitors=4)

    accepted = [c for c in resolved if c.status.value == "accepted"]
    skipped = [c for c in resolved if c.status.value == "skipped_duplicate"]

    assert len(accepted) == 4
    assert len(skipped) == 1
    assert skipped[0].name == "notion.so"
    assert meets_minimum is True


def test_min_competitor_gate_fails_when_too_many_duplicates() -> None:
    target = make_competitor("Notero", "notero.com", "AI-native note-taking app", is_target=True)
    proposed = [
        make_competitor("Notion", "notion.so", "All-in-one workspace"),
        make_competitor("Notion", "notion.so", "exact duplicate"),
        make_competitor("Coda", "coda.io", "Docs that work like apps"),
    ]

    _, resolved, meets_minimum = resolve_intake(target, proposed, min_competitors=4)

    accepted = [c for c in resolved if c.status.value == "accepted"]
    assert len(accepted) == 2
    assert meets_minimum is False
