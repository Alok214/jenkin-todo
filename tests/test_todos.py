import pytest
from fastapi.testclient import TestClient
from todos import app, todos

client = TestClient(app)

@pytest.fixture(autouse=True)
def clear_todos():
    todos.clear()
    # reset id counter
    import todos as todos_module
    todos_module._next_id = 1
    yield
    todos.clear()

def test_root():
    r = client.get("/")
    assert r.status_code == 200
    assert "Todo API" in r.json()["message"]

def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}

def test_create_and_list():
    r = client.post("/todos", json={"title": "Buy milk", "description": "2L", "completed": False})
    assert r.status_code == 201
    data = r.json()
    assert data["id"] == 1
    assert data["title"] == "Buy milk"

    r2 = client.get("/todos")
    assert r2.status_code == 200
    assert len(r2.json()) == 1

def test_get_todo_not_found():
    r = client.get("/todos/999")
    assert r.status_code == 404

def test_update_todo():
    c = client.post("/todos", json={"title": "Old"}).json()
    tid = c["id"]
    r = client.put(f"/todos/{tid}", json={"title": "New", "description": "updated", "completed": True})
    assert r.status_code == 200
    assert r.json()["title"] == "New"
    assert r.json()["completed"] is True

def test_delete_todo():
    c = client.post("/todos", json={"title": "ToDelete"}).json()
    tid = c["id"]
    r = client.delete(f"/todos/{tid}")
    assert r.status_code == 200
    assert "deleted" in r.json()["message"]
    assert client.get(f"/todos/{tid}").status_code == 404

def test_validation_empty_title():
    r = client.post("/todos", json={"title": ""})
    assert r.status_code == 422
