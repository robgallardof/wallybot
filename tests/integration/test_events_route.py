import pyotp
import pytest

pytestmark = pytest.mark.integration


def enroll(client, settings) -> None:
    body = {
        "username": "admin",
        "password": "correct-horse-battery-staple",
        "bootstrap_token": settings.bootstrap_token.get_secret_value(),
    }
    started = client.post("/api/auth/setup/start", json=body)
    assert started.status_code == 200, started.text
    enrollment = started.json()
    finished = client.post(
        "/api/auth/setup/finish",
        json={
            "bootstrap_token": body["bootstrap_token"],
            "challenge": enrollment["challenge"],
            "code": pyotp.TOTP(enrollment["secret"]).now(),
        },
    )
    assert finished.status_code == 200, finished.text


def insert_event(
    db, event_id: str, timestamp: int, event: str = "TEST_EVENT", message: str = "test message"
) -> None:
    db.execute(
        "INSERT INTO events (id, timestamp, actor, event, message, correlation_id) "
        "VALUES (%s, %s, NULL, %s, %s, %s)",
        (event_id, timestamp, event, message, event_id),
    )


def test_events_route_requires_auth(client) -> None:
    assert client.get("/api/events").status_code == 401


def test_events_lists_newest_first_and_paginates_with_a_cursor(client, settings, db) -> None:
    enroll(client, settings)
    for i in range(5):
        insert_event(db, f"page-{i}", 1000 + i, event="PAGETEST")

    first = client.get("/api/events", params={"event": "PAGETEST", "limit": 2})
    assert first.status_code == 200, first.text
    first_body = first.json()
    assert [row["timestamp"] for row in first_body["rows"]] == [1004, 1003]
    assert first_body["next_before"] is not None

    second = client.get(
        "/api/events",
        params={"event": "PAGETEST", "limit": 2, "before": first_body["next_before"]},
    )
    second_body = second.json()
    assert [row["timestamp"] for row in second_body["rows"]] == [1002, 1001]
    assert second_body["next_before"] is not None

    third = client.get(
        "/api/events",
        params={"event": "PAGETEST", "limit": 2, "before": second_body["next_before"]},
    )
    third_body = third.json()
    assert [row["timestamp"] for row in third_body["rows"]] == [1000]
    assert third_body["next_before"] is None

    seen_ids = {row["id"] for page in (first_body, second_body, third_body) for row in page["rows"]}
    assert seen_ids == {f"page-{i}" for i in range(5)}


def test_events_cursor_tie_breaks_on_id_when_timestamps_collide(client, settings, db) -> None:
    enroll(client, settings)
    insert_event(db, "tie-a", 2000, event="TIETEST", message="first")
    insert_event(db, "tie-b", 2000, event="TIETEST", message="second")

    first = client.get("/api/events", params={"event": "TIETEST", "limit": 1})
    first_body = first.json()
    assert [row["id"] for row in first_body["rows"]] == ["tie-b"]
    assert first_body["next_before"] == "2000:tie-b"

    second = client.get(
        "/api/events",
        params={"event": "TIETEST", "limit": 1, "before": first_body["next_before"]},
    )
    second_body = second.json()
    assert [row["id"] for row in second_body["rows"]] == ["tie-a"]
    assert second_body["next_before"] is None


def test_events_search_matches_event_code_or_message(client, settings, db) -> None:
    enroll(client, settings)
    insert_event(db, "search-1", 3000, event="SEARCHABLE_CODE", message="unrelated text")
    insert_event(db, "search-2", 3001, event="OTHER_CODE", message="contains marker-xyz here")

    by_event = client.get("/api/events", params={"q": "searchable"}).json()
    assert [row["id"] for row in by_event["rows"]] == ["search-1"]

    by_message = client.get("/api/events", params={"q": "marker-xyz"}).json()
    assert [row["id"] for row in by_message["rows"]] == ["search-2"]


def test_events_event_type_filter_is_an_exact_match(client, settings, db) -> None:
    enroll(client, settings)
    insert_event(db, "type-a", 4000, event="TYPE_ALPHA")
    insert_event(db, "type-b", 4001, event="TYPE_BETA")

    filtered = client.get("/api/events", params={"event": "TYPE_ALPHA"}).json()
    assert [row["id"] for row in filtered["rows"]] == ["type-a"]


def test_events_limit_is_bounded_to_200(client, settings) -> None:
    enroll(client, settings)

    assert client.get("/api/events", params={"limit": 201}).status_code == 422
    assert client.get("/api/events", params={"limit": 0}).status_code == 422


def test_events_rejects_a_malformed_cursor(client, settings) -> None:
    enroll(client, settings)

    response = client.get("/api/events", params={"before": "not-a-cursor"})

    assert response.status_code == 400


def test_export_requires_auth(client) -> None:
    assert client.get("/api/events/export").status_code == 401


def test_export_defaults_to_csv_and_includes_actor_and_correlation_id(client, settings, db) -> None:
    enroll(client, settings)
    db.execute(
        "INSERT INTO events (id, timestamp, actor, event, message, correlation_id) "
        "VALUES (%s, %s, %s, %s, %s, %s)",
        ("export-csv-1", 5000, "admin-id", "EXPORT_TEST", "export test message", "corr-1"),
    )

    response = client.get("/api/events/export", params={"since": 4999, "until": 5001})

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    lines = response.text.strip().splitlines()
    assert lines[0] == "id,timestamp,actor,event,message,correlation_id"
    assert lines[1].startswith("export-csv-1,")
    assert "admin-id" in lines[1]
    assert "corr-1" in lines[1]


def test_export_json_returns_the_audit_fields(client, settings, db) -> None:
    enroll(client, settings)
    db.execute(
        "INSERT INTO events (id, timestamp, actor, event, message, correlation_id) "
        "VALUES (%s, %s, %s, %s, %s, %s)",
        ("export-json-1", 5001, None, "EXPORT_TEST_JSON", "json export message", "corr-2"),
    )

    response = client.get("/api/events/export", params={"format": "json"})

    assert response.status_code == 200
    rows = response.json()
    matching = [row for row in rows if row["id"] == "export-json-1"]
    assert len(matching) == 1
    row = matching[0]
    assert row["actor"] is None
    assert row["event"] == "EXPORT_TEST_JSON"
    assert row["correlation_id"] == "corr-2"


def test_export_since_and_until_bound_the_window(client, settings, db) -> None:
    enroll(client, settings)
    insert_event(db, "window-before", 6000, event="WINDOWTEST")
    insert_event(db, "window-inside", 6100, event="WINDOWTEST")
    insert_event(db, "window-after", 6200, event="WINDOWTEST")

    response = client.get(
        "/api/events/export",
        params={"format": "json", "since": 6050, "until": 6150},
    )

    ids = {row["id"] for row in response.json()}
    assert ids == {"window-inside"}


def test_export_with_no_matching_events_is_only_a_header_row(client, settings) -> None:
    enroll(client, settings)

    response = client.get("/api/events/export", params={"until": 1})

    lines = response.text.strip().splitlines()
    assert lines == ["id,timestamp,actor,event,message,correlation_id"]
