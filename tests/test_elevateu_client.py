import requests

import connectors.elevateu_client as eu
from connectors.elevateu_client import ElevateUClient, summarize_assignments, summarize_jobs


class FakeResp:
    def __init__(self, status, body):
        self.status_code = status
        self.ok = 200 <= status < 300
        self._body = body

    def json(self):
        return self._body


def fake_requests(monkeypatch, status=200, body=None, raise_exc=None):
    calls = []

    def request(method, url, headers=None, timeout=None, **kwargs):
        calls.append({"method": method, "url": url, "headers": headers, **kwargs})
        if raise_exc:
            raise raise_exc
        return FakeResp(status, body)

    monkeypatch.setattr(eu.requests, "request", request)
    return calls


def test_feed_uses_verified_route_and_bearer_token(monkeypatch):
    feed = {"jobs": [{"id": f"j{i}", "title": f"Engineer {i}", "company": "Acme", "grade": "A"} for i in range(7)], "total": 7}
    calls = fake_requests(monkeypatch, body=feed)
    result = summarize_jobs(ElevateUClient("http://x", "tok").job_feed())

    assert calls[0]["url"] == "http://x/api/v1/job/jobs/feed"
    assert calls[0]["headers"] == {"Authorization": "Bearer tok"}
    assert len(result["jobs"]) == 5 and result["jobs"][0] == {"n": 1, "id": "j0", "summary": "Engineer 0 at Acme, grade A", "apply_url": None}
    assert result["response"].startswith("7 jobs.")


def test_backend_down_and_bad_token_are_plain_failures(monkeypatch):
    fake_requests(monkeypatch, raise_exc=requests.ConnectionError())
    assert "isn't running" in ElevateUClient("http://x").job_feed()["response"]
    fake_requests(monkeypatch, status=401, body={})
    assert "rejected" in ElevateUClient("http://x").profile()["response"]


def test_assignments_summary(monkeypatch):
    fake_requests(monkeypatch, body={"assignments": [{"title": "Lab 3", "course_name": "CSCE 4430", "due_at": "2026-09-20"}], "count": 1})
    result = summarize_assignments(ElevateUClient("http://x").assignments())
    assert result["response"] == "1 assignments. Lab 3 for CSCE 4430, due 2026-09-20"


def test_update_application_sends_status(monkeypatch):
    calls = fake_requests(monkeypatch, body={"updated": True})
    ElevateUClient("http://x").update_application("a1", "applied")
    assert calls[0]["method"] == "PUT" and calls[0]["url"].endswith("/api/v1/job/applications/a1")
    assert calls[0]["json"] == {"status": "applied"}
