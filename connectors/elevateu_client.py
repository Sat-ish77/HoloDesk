"""ElevateU API client (FastAPI backend in the study-helper repo).

Routes were read from study-helper/backend/main.py and jobhunt/routers/*.py.
Auth is `Authorization: Bearer <token>`: a Supabase session JWT in production,
or `dev-token` against a local backend started with ALLOW_DEV_AUTH=true.
Every method returns a dict and never raises.
"""

from __future__ import annotations

import os
from typing import Any

import requests


class ElevateUClient:
    TIMEOUT = 20

    def __init__(self, base_url: str | None = None, token: str | None = None):
        self.base_url = (base_url or os.getenv("ELEVATEU_API_BASE", "http://127.0.0.1:8000")).rstrip("/")
        self.token = token or os.getenv("ELEVATEU_TOKEN", "dev-token")

    def _request(self, method: str, path: str, **kwargs) -> dict[str, Any]:
        try:
            resp = requests.request(
                method,
                self.base_url + path,
                headers={"Authorization": f"Bearer {self.token}"},
                timeout=self.TIMEOUT,
                **kwargs,
            )
        except requests.ConnectionError:
            return {"success": False, "response": f"The ElevateU backend isn't running at {self.base_url}."}
        except requests.RequestException as exc:
            return {"success": False, "response": f"ElevateU request failed: {exc}"}
        if resp.status_code == 401:
            return {"success": False, "response": "ElevateU rejected my login token."}
        if not resp.ok:
            return {"success": False, "response": f"ElevateU returned HTTP {resp.status_code}."}
        try:
            return {"success": True, "data": resp.json()}
        except ValueError:
            return {"success": False, "response": "ElevateU sent back something that isn't JSON."}

    def job_feed(self, limit: int = 20) -> dict:
        return self._request("GET", "/api/v1/job/jobs/feed", params={"limit": limit})

    def search_jobs(self, role: str, location: str = "", limit: int = 20) -> dict:
        return self._request("GET", "/api/v1/job/jobs/search", params={"role": role, "location": location, "limit": limit})

    def job_workspace(self, job_id: str) -> dict:
        return self._request("GET", f"/api/v1/job/jobs/{job_id}/workspace")

    def list_applications(self) -> dict:
        return self._request("GET", "/api/v1/job/applications")

    def update_application(self, application_id: str, status: str) -> dict:
        return self._request("PUT", f"/api/v1/job/applications/{application_id}", json={"status": status})

    def profile(self) -> dict:
        return self._request("GET", "/api/v1/job/profile")

    def assignments(self) -> dict:
        return self._request("GET", "/api/v1/assignments")

    def autopilot_status(self) -> dict:
        return self._request("GET", "/api/v1/job/autopilot/status")


def _job_line(job: dict) -> str:
    inner = job.get("jobs") if isinstance(job.get("jobs"), dict) else job
    title = inner.get("title") or "Untitled role"
    company = inner.get("company") or inner.get("company_name") or "unknown company"
    grade = job.get("grade") or inner.get("grade")
    return f"{title} at {company}" + (f", grade {grade}" if grade else "")


def _items(data: Any, *keys: str) -> list:
    if isinstance(data, list):
        return data
    for key in keys:
        if isinstance(data.get(key), list):
            return data[key]
    return []


def summarize_jobs(result: dict, top: int = 5) -> dict:
    """Shape a feed/search result for speaking: at most `top` jobs, with ids kept for follow-ups."""
    if not result.get("success"):
        return result
    jobs = _items(result["data"], "jobs", "results")
    if not jobs:
        return {"success": True, "response": "ElevateU has no jobs for that right now.", "jobs": []}
    picked = [
        {"n": i + 1, "id": j.get("id") or j.get("job_id"), "summary": _job_line(j), "apply_url": j.get("apply_url")}
        for i, j in enumerate(jobs[:top])
    ]
    spoken = "; ".join(f"{p['n']}. {p['summary']}" for p in picked)
    return {"success": True, "response": f"{len(jobs)} jobs. Top {len(picked)}: {spoken}", "jobs": picked}


def summarize_applications(result: dict, top: int = 5) -> dict:
    if not result.get("success"):
        return result
    apps = _items(result["data"], "applications")
    if not apps:
        return {"success": True, "response": "No applications tracked in ElevateU yet.", "applications": []}
    picked = [{"id": a.get("id"), "status": a.get("status"), "summary": _job_line(a)} for a in apps[:top]]
    spoken = "; ".join(f"{p['summary']} ({p['status']})" for p in picked)
    return {"success": True, "response": f"{len(apps)} applications. {spoken}", "applications": picked}


def summarize_assignments(result: dict, top: int = 5) -> dict:
    if not result.get("success"):
        return result
    items = _items(result["data"], "assignments", "items")
    if not items:
        return {"success": True, "response": "No assignments in ElevateU.", "assignments": []}
    picked = [
        {"title": a.get("title") or a.get("name"), "course": a.get("course_name") or a.get("course"), "due": a.get("due_at") or a.get("due_date")}
        for a in items[:top]
    ]
    spoken = "; ".join(
        f"{p['title']}" + (f" for {p['course']}" if p["course"] else "") + (f", due {p['due']}" if p["due"] else "")
        for p in picked
    )
    return {"success": True, "response": f"{len(items)} assignments. {spoken}", "assignments": picked}
