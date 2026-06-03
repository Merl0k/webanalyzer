"""Stable API tests for WebAnalyzer v3."""

from __future__ import annotations

from tests.conftest import create_saved_search, register_and_login


def test_health_endpoint(client):
    resp = client.get("/api/v1/health")

    assert resp.status_code == 200

    data = resp.get_json()

    assert data["status"] in ("ok", "degraded")
    assert data["db"] in ("ok", "error")
    assert "redis" in data
    assert "celery" in data
    assert data["version"] == "3.0.0"


def test_openapi_json_and_docs(client):
    resp = client.get("/api/v1/openapi.json")

    assert resp.status_code == 200

    data = resp.get_json()

    assert data["openapi"].startswith("3.")
    assert data["info"]["title"] == "WebAnalyzer v3 API"
    assert "/api/v1/analyze" in data["paths"]

    docs = client.get("/api/v1/docs")

    assert docs.status_code == 200
    assert b"swagger" in docs.data.lower() or b"WebAnalyzer" in docs.data


def test_register_login_me_logout_flow(client):
    user = register_and_login(client)

    assert user["email"].startswith("pytest+")

    me = client.get("/api/v1/auth/me")

    assert me.status_code == 200
    assert me.get_json()["email"] == user["email"]

    logout = client.post("/api/v1/auth/logout")

    assert logout.status_code == 200

    me_after_logout = client.get("/api/v1/auth/me")

    assert me_after_logout.status_code == 401


def test_profile_theme_and_api_keys(auth_client):
    client, _user = auth_client

    theme_resp = client.post("/api/v1/profile/theme", json={"theme": "ocean"})

    assert theme_resp.status_code == 200
    assert theme_resp.get_json()["ok"] is True

    save_key = client.post(
        "/api/v1/profile/keys",
        json={
            "provider": "groq",
            "key": "gsk_test_key_for_pytest",
            "model": "llama-3.3-70b-versatile",
        },
    )

    assert save_key.status_code == 200
    assert save_key.get_json()["provider"] == "groq"

    keys = client.get("/api/v1/profile/keys")

    assert keys.status_code == 200
    assert any(k["provider"] == "groq" for k in keys.get_json())

    delete_key = client.delete("/api/v1/profile/keys/groq")

    assert delete_key.status_code == 200
    assert delete_key.get_json()["ok"] is True


def test_history_detail_export_and_share(auth_client):
    client, user = auth_client

    search_id = create_saved_search(user["id"], query="PDF export test")

    history = client.get("/api/v1/history?limit=10&offset=0")

    assert history.status_code == 200
    assert any(row["id"] == search_id for row in history.get_json())

    detail = client.get(f"/api/v1/history/{search_id}")

    assert detail.status_code == 200
    assert detail.get_json()["query"] == "PDF export test"

    export_json = client.get(f"/api/v1/history/{search_id}/export/json")

    assert export_json.status_code == 200
    assert export_json.content_type.startswith("application/json")

    export_md = client.get(f"/api/v1/history/{search_id}/export/markdown")

    assert export_md.status_code == 200
    assert "text/markdown" in export_md.content_type

    export_pdf = client.get(f"/api/v1/history/{search_id}/export/pdf")

    assert export_pdf.status_code == 200
    assert export_pdf.content_type.startswith("application/pdf")
    assert export_pdf.data[:4] == b"%PDF"

    share = client.post(f"/api/v1/history/{search_id}/share")

    assert share.status_code == 200

    token = share.get_json()["token"]
    public = client.get(f"/api/v1/share/{token}")

    assert public.status_code == 200
    assert public.get_json()["id"] == search_id


def test_compare_two_results(auth_client):
    client, user = auth_client

    first_id = create_saved_search(user["id"], query="Перший аналіз")
    second_id = create_saved_search(user["id"], query="Другий аналіз")

    resp = client.post(
        "/api/v1/compare",
        json={"ids": [first_id, second_id]},
    )

    assert resp.status_code == 200

    data = resp.get_json()

    assert data["queries"] == ["Перший аналіз", "Другий аналіз"]
    assert len(data["sentiments"]) == 2
    assert len(data["sources_cnt"]) == 2


def test_tags_create_attach_filter_remove(auth_client):
    client, user = auth_client

    search_id = create_saved_search(user["id"], query="Tagged result")

    create_tag = client.post(
        "/api/v1/tags",
        json={"name": "AI", "color": "#4fffb0"},
    )

    assert create_tag.status_code == 200

    tag = create_tag.get_json()
    tag_id = tag["id"]

    list_tags = client.get("/api/v1/tags")

    assert list_tags.status_code == 200
    assert any(t["id"] == tag_id for t in list_tags.get_json())

    attach = client.post(f"/api/v1/history/{search_id}/tags/{tag_id}")

    assert attach.status_code == 200

    detail = client.get(f"/api/v1/history/{search_id}")

    assert detail.status_code == 200
    assert any(t["id"] == tag_id for t in detail.get_json()["tags"])

    filtered = client.get(f"/api/v1/history?tag_id={tag_id}")

    assert filtered.status_code == 200
    assert any(row["id"] == search_id for row in filtered.get_json())

    remove = client.delete(f"/api/v1/history/{search_id}/tags/{tag_id}")

    assert remove.status_code == 200

    detail_after_remove = client.get(f"/api/v1/history/{search_id}")

    assert detail_after_remove.status_code == 200
    assert not any(t["id"] == tag_id for t in detail_after_remove.get_json()["tags"])


def test_user_cannot_access_another_users_history(app):
    first_client = app.test_client()
    first_user = register_and_login(first_client)

    foreign_search_id = create_saved_search(
        first_user["id"],
        query="Foreign private result",
    )

    second_client = app.test_client()
    second_user = register_and_login(second_client)

    own_search_id = create_saved_search(
        second_user["id"],
        query="Own result",
    )

    foreign_detail = second_client.get(f"/api/v1/history/{foreign_search_id}")

    assert foreign_detail.status_code == 404

    foreign_export = second_client.get(
        f"/api/v1/history/{foreign_search_id}/export/json"
    )

    assert foreign_export.status_code == 404

    compare = second_client.post(
        "/api/v1/compare",
        json={"ids": [foreign_search_id, own_search_id]},
    )

    assert compare.status_code == 404

def test_collections_create_add_filter_remove_delete(auth_client):
    client, user = auth_client

    search_id = create_saved_search(user["id"], query="Collection result")

    create_col = client.post(
        "/api/v1/collections",
        json={
            "name": "Диплом",
            "description": "Матеріали для дипломної роботи",
        },
    )

    assert create_col.status_code == 200

    col = create_col.get_json()
    col_id = col["id"]

    add = client.post(f"/api/v1/collections/{col_id}/add/{search_id}")

    assert add.status_code == 200

    detail = client.get(f"/api/v1/history/{search_id}")

    assert detail.status_code == 200
    assert any(c["id"] == col_id for c in detail.get_json()["collections"])

    filtered = client.get(f"/api/v1/history?collection_id={col_id}")

    assert filtered.status_code == 200
    assert any(row["id"] == search_id for row in filtered.get_json())

    remove = client.delete(f"/api/v1/collections/{col_id}/remove/{search_id}")

    assert remove.status_code == 200

    detail_after_remove = client.get(f"/api/v1/history/{search_id}")

    assert detail_after_remove.status_code == 200
    assert not any(c["id"] == col_id for c in detail_after_remove.get_json()["collections"])

    delete_col = client.delete(f"/api/v1/collections/{col_id}")

    assert delete_col.status_code == 200