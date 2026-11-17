"""ASTRA server + engine tests (bina internet)."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "astra"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "studio"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))


def test_engine_generates_all():
    import astra as A
    for name in A.GENERATORS:
        arr, meta = A.build(A.SoundRequest(description=name, duration=0.6))
        assert len(arr) > 1000, name
        info = A.qa(arr)
        assert info["ok"], (name, info)


def test_server_endpoints():
    from fastapi.testclient import TestClient
    import server
    c = TestClient(server.app)
    assert c.get("/api/health").json()["status"] == "ok"
    assert c.get("/api/sounds").json()["total"] >= 25
    r = c.post("/api/sound", json={"text": "mitti par kadam", "dur": 1.0})
    assert r.status_code == 200 and r.json()["qa"]["ok"]
    s = c.post("/api/stories", json={"title": "t", "scenes": []})
    assert s.status_code == 200
    assert c.get("/").status_code == 200
