"""Reviewer feedback: rename / delete / summarise folders, Recycle bin, AI folder suggestion, folder search."""
from app.demo import SAMPLES
from conftest import approve_suggestions, make_user_headers, upload

ASSIGNMENT = next(s for s in SAMPLES if s["filename"] == "Database_Assignment.pdf")["text"]
INVOICE = next(s for s in SAMPLES if s["filename"] == "Invoice_2026.pdf")["text"]


def add_and_approve(client, headers, filename, text):
    file_id = upload(client, headers, filename, text.encode()).get_json()["file_id"]
    approve_suggestions(client, headers, file_id)
    return file_id


def folder_id_by_path(client, headers, path):
    def walk(nodes):
        for node in nodes:
            if node["path"] == path:
                return node["folder_id"]
            found = walk(node["children"])
            if found:
                return found
        return None
    return walk(client.get("/api/folders", headers=headers).get_json())


# ---------------------------------------------------------------- folders
def test_rename_folder(client, auth):
    add_and_approve(client, auth, "assignment.txt", ASSIGNMENT)
    folder_id = folder_id_by_path(client, auth, "University/Year 2")
    res = client.patch(f"/api/folders/{folder_id}", headers=auth, json={"name": "Second Year"})
    assert res.status_code == 200
    assert res.get_json()["path"] == "University/Second Year"
    doc = client.get("/api/documents", headers=auth).get_json()["items"][0]
    assert doc["folder_path"] == "University/Second Year/Semester 1/Database Systems"


def test_rename_folder_rejects_empty_and_duplicate_names(client, auth):
    a = client.post("/api/folders", headers=auth, json={"name": "Alpha"}).get_json()
    client.post("/api/folders", headers=auth, json={"name": "Beta"})
    assert client.patch(f"/api/folders/{a['folder_id']}", headers=auth, json={"name": "  "}).status_code == 400
    assert client.patch(f"/api/folders/{a['folder_id']}", headers=auth, json={"name": "beta"}).status_code == 409
    # renaming to the same name with different capitals is fine
    assert client.patch(f"/api/folders/{a['folder_id']}", headers=auth, json={"name": "ALPHA"}).status_code == 200


def test_delete_folder_moves_documents_to_recycle_bin(client, auth):
    file_id = add_and_approve(client, auth, "assignment.txt", ASSIGNMENT)
    folder_id = folder_id_by_path(client, auth, "University")
    res = client.delete(f"/api/folders/{folder_id}", headers=auth)
    assert res.status_code == 200
    assert res.get_json() == {"deleted_folders": 4, "documents_moved_to_recycle_bin": 1}
    assert client.get("/api/folders", headers=auth).get_json() == []
    trash = client.get("/api/trash", headers=auth).get_json()
    assert [d["file_id"] for d in trash["items"]] == [file_id]
    assert trash["items"][0]["deleted_from_path"] == "University/Year 2/Semester 1/Database Systems"

    # Restoring re-creates the folders it came from.
    restored = client.post(f"/api/documents/{file_id}/restore", headers=auth).get_json()
    assert restored["status"] == "STORED"
    assert restored["folder_path"] == "University/Year 2/Semester 1/Database Systems"


def test_folder_summary(client, auth):
    add_and_approve(client, auth, "assignment.txt", ASSIGNMENT)
    add_and_approve(client, auth, "invoice.txt", INVOICE)
    folder_id = folder_id_by_path(client, auth, "University")
    summary = client.get(f"/api/folders/{folder_id}/summary", headers=auth).get_json()
    assert summary["document_count"] == 1          # includes documents in subfolders
    assert summary["subfolder_count"] == 3
    assert summary["categories"] == [{"category": "University", "count": 1}]
    assert "1 document" in summary["overview"] and summary["source"] == "local"
    assert summary["documents"][0]["summary"]

    empty = client.post("/api/folders", headers=auth, json={"name": "Empty"}).get_json()
    assert "is empty" in client.get(f"/api/folders/{empty['folder_id']}/summary", headers=auth).get_json()["overview"]


def test_other_users_cannot_touch_my_folders(client, auth):
    folder = client.post("/api/folders", headers=auth, json={"name": "Private"}).get_json()
    other = make_user_headers(client, "other@example.com")
    fid = folder["folder_id"]
    assert client.patch(f"/api/folders/{fid}", headers=other, json={"name": "x"}).status_code == 404
    assert client.delete(f"/api/folders/{fid}", headers=other).status_code == 404
    assert client.get(f"/api/folders/{fid}/summary", headers=other).status_code == 404


# ---------------------------------------------------------------- recycle bin
def test_recycle_bin_hides_restores_and_empties(client, auth):
    file_id = add_and_approve(client, auth, "assignment.txt", ASSIGNMENT)
    assert client.post(f"/api/documents/{file_id}/trash", headers=auth).get_json()["status"] == "DELETED"

    # Hidden everywhere except the Recycle bin
    assert client.get("/api/documents", headers=auth).get_json()["total"] == 0
    assert client.get("/api/documents?status=ALL", headers=auth).get_json()["total"] == 0
    assert client.post("/api/search", headers=auth, json={"query": "database"}).get_json()["results"] == []
    assert client.get("/api/dashboard/stats", headers=auth).get_json()["in_recycle_bin"] == 1
    assert client.post(f"/api/documents/{file_id}/approve", headers=auth,
                       json={"filename": "x", "folder_path": ["x"]}).status_code == 409

    client.post(f"/api/documents/{file_id}/restore", headers=auth)
    assert client.get("/api/documents", headers=auth).get_json()["total"] == 1

    client.post(f"/api/documents/{file_id}/trash", headers=auth)
    assert client.delete("/api/trash", headers=auth).get_json() == {"deleted": 1}
    assert client.get(f"/api/documents/{file_id}", headers=auth).status_code == 404


def test_file_in_recycle_bin_can_be_uploaded_again(client, auth):
    file_id = add_and_approve(client, auth, "assignment.txt", ASSIGNMENT)
    client.post(f"/api/documents/{file_id}/trash", headers=auth)
    assert upload(client, auth, "assignment.txt", ASSIGNMENT.encode()).status_code == 202


def test_restore_only_works_for_deleted_documents(client, auth):
    file_id = add_and_approve(client, auth, "assignment.txt", ASSIGNMENT)
    assert client.post(f"/api/documents/{file_id}/restore", headers=auth).status_code == 409


# ---------------------------------------------------------------- AI folder suggestion
def test_ai_recommends_an_existing_folder(client, auth):
    """Teacher feedback: the AI should suggest one of the folders that already exist."""
    add_and_approve(client, auth, "assignment.txt", ASSIGNMENT)
    lab = ("NIT2102 Database Systems\nLab 5: SQL joins and normalisation. Write SELECT queries with INNER JOIN "
           "and LEFT JOIN on the Library database. Explain third normal form.")
    file_id = upload(client, auth, "SQL_Lab.txt", lab.encode()).get_json()["file_id"]
    analysis = client.get(f"/api/documents/{file_id}/analysis", headers=auth).get_json()
    best = analysis["folder_recommendations"][0]
    assert best["path"] == ["University", "Year 2", "Semester 1", "Database Systems"]
    assert best["is_new"] is False and best["folder_id"] and best["reason"]


def test_ai_suggests_a_new_folder_when_nothing_fits(client, auth):
    file_id = upload(client, auth, "assignment.txt", ASSIGNMENT.encode()).get_json()["file_id"]
    best = client.get(f"/api/documents/{file_id}/analysis", headers=auth).get_json()["folder_recommendations"][0]
    assert best["is_new"] is True
    assert best["path"] == ["University", "Year 2", "Semester 1", "Database Systems"]


# ---------------------------------------------------------------- AI search finds folders
def test_search_returns_matching_folders(client, auth):
    add_and_approve(client, auth, "assignment.txt", ASSIGNMENT)
    add_and_approve(client, auth, "invoice.txt", INVOICE)
    res = client.post("/api/search", headers=auth, json={"query": "database"}).get_json()
    assert res["folders"][0]["path"] == "University/Year 2/Semester 1/Database Systems"
    assert res["folders"][0]["document_count"] == 1
    invoices = client.post("/api/search", headers=auth, json={"query": "invoices"}).get_json()["folders"]
    assert invoices[0]["path"] == "Finance/Invoices"
    assert invoices[0]["document_count"] == 1  # the invoice is in the 2026 subfolder


# ---------------------------------------------------------------- database upgrade
def test_upgrade_adds_new_columns_to_an_old_database(app):
    """A database made by v0.1 (no Recycle bin columns) is upgraded without losing data."""
    import sqlalchemy as sa

    from app.extensions import db
    from app.upgrade import upgrade_database

    with db.engine.begin() as conn:
        conn.execute(sa.text("ALTER TABLE files DROP COLUMN deleted_at"))
        conn.execute(sa.text("ALTER TABLE files DROP COLUMN deleted_from_path"))
    assert upgrade_database() == ["added files.deleted_at", "added files.deleted_from_path"]
    assert upgrade_database() == []  # running it again changes nothing


# ---------------------------------------------------------------- GPT folder choice
def use_fake_gpt(client, reply: dict):
    """Swap the app's analyser for the OpenAI one with a fake client that always gives `reply`."""
    import json
    from types import SimpleNamespace

    from app.services.ai.openai_provider import OpenAIAnalyzer

    def create(**kwargs):
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(reply)))])

    fake = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    client.application.extensions["analyzer"] = OpenAIAnalyzer("test-key", "gpt-test", 4000, client=fake)


LAB = ("NIT2102 Database Systems\nLab 5: SQL joins and normalisation. Write SELECT queries with INNER JOIN "
       "and LEFT JOIN on the Library database. Explain third normal form.")
GPT_LAB = {"title": "SQL Lab 5", "summary": "Joins.", "category": "University", "subject": "Database Systems",
           "document_type": "Lab Sheet", "keywords": ["SQL", "joins"], "suggested_filename": "SQL_Lab_5",
           "confidence": 0.9}


def test_gpt_choice_of_an_existing_folder_is_the_best_match_with_its_reason(client, auth):
    add_and_approve(client, auth, "assignment.txt", ASSIGNMENT)
    add_and_approve(client, auth, "invoice.txt", INVOICE)
    use_fake_gpt(client, {**GPT_LAB, "existing_folder": "University/Year 2/Semester 1/Database Systems",
                          "suggested_folder_path": [], "folder_reason": "It is a lab for the same course."})
    file_id = upload(client, auth, "SQL_Lab.txt", LAB.encode()).get_json()["file_id"]
    best = client.get(f"/api/documents/{file_id}/analysis", headers=auth).get_json()["folder_recommendations"][0]
    assert best["path"] == ["University", "Year 2", "Semester 1", "Database Systems"]
    assert best["is_new"] is False and best["score"] >= 0.6
    assert best["reason"] == "GPT read the document: It is a lab for the same course."


def test_gpt_new_folder_beats_a_folder_that_only_shares_words(client, auth):
    add_and_approve(client, auth, "assignment.txt", ASSIGNMENT)
    use_fake_gpt(client, {**GPT_LAB, "subject": "Computer Networks", "existing_folder": "",
                          "suggested_folder_path": ["University", "Year 2", "Semester 1", "Computer Networks"],
                          "folder_reason": "No folder for Computer Networks yet."})
    lab = "Computer Networks lab: subnetting, TCP handshakes and routing tables for the university network." * 2
    file_id = upload(client, auth, "Networks_Lab.txt", lab.encode()).get_json()["file_id"]
    best = client.get(f"/api/documents/{file_id}/analysis", headers=auth).get_json()["folder_recommendations"][0]
    assert best["is_new"] is True
    assert best["path"] == ["University", "Year 2", "Semester 1", "Computer Networks"]
    assert "No folder for Computer Networks yet." in best["reason"]
