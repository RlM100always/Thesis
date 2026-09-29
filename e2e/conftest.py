"""End-to-end fixtures: a real API, the built frontend, and a real browser.

Nothing here is mocked. The stack is the production API (``AUTH_MODE=jwt``, a
throwaway SQLite database) plus the built frontend served by ``vite preview``,
driven through Microsoft Edge by Playwright. Run with:

    python -m pytest e2e -q

Prerequisites: ``npm run build`` in ``frontend/`` (the tests use ``dist/``),
``pip install playwright`` and Microsoft Edge. Ports 8000 (API) and 5174 (web)
must be free; 5174 is one of the origins the API's CORS allows.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
from datetime import date, timedelta
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
API = "http://127.0.0.1:8000"
WEB = "http://localhost:5174"
PASSWORD = "correct horse battery"


def _wait(url: str, timeout: float = 90) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            urllib.request.urlopen(url, timeout=3)
            return
        except (urllib.error.URLError, ConnectionError, TimeoutError):
            time.sleep(0.5)
    raise RuntimeError(f"{url} did not come up within {timeout}s")


def _stop(process: subprocess.Popen) -> None:
    if process.poll() is None:
        if os.name == "nt":  # kill the whole tree (npx spawns node)
            subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], capture_output=True)
        else:
            process.terminate()


@pytest.fixture(scope="session")
def stack(tmp_path_factory):
    if not (ROOT / "frontend" / "dist" / "index.html").exists():
        pytest.exit("Build the frontend first: cd frontend && npm run build", returncode=2)
    workdir = tmp_path_factory.mktemp("e2e")
    env = {**os.environ, "DATABASE_URL": f"sqlite:///{(workdir / 'e2e.db').as_posix()}", "AUTH_MODE": "jwt"}
    api_log = open(workdir / "api.log", "w", encoding="utf-8")
    web_log = open(workdir / "web.log", "w", encoding="utf-8")
    api = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "api.main:app", "--port", "8000"],
        cwd=ROOT, env=env, stdout=api_log, stderr=subprocess.STDOUT)
    web = subprocess.Popen(
        ["npx.cmd" if os.name == "nt" else "npx", "vite", "preview", "--port", "5174", "--strictPort"],
        cwd=ROOT / "frontend", stdout=web_log, stderr=subprocess.STDOUT)
    try:
        _wait(f"{API}/health")
        _wait(WEB)
        yield {"api": API, "web": WEB, "logs": workdir}
    finally:
        _stop(web)
        _stop(api)


@pytest.fixture(scope="session")
def browser(stack):
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel="msedge", headless=True)
        yield browser
        browser.close()


class Session:
    """One browser context (own storage, own cookies) plus the errors it saw."""

    def __init__(self, browser, viewport):
        self.context = browser.new_context(viewport=viewport, locale="bn-BD", timezone_id="Asia/Dhaka")
        self.page = self.context.new_page()
        self.errors: list[str] = []
        self.page.on("pageerror", lambda e: self.errors.append(f"pageerror: {e}"))
        self.page.on("console", lambda m: m.type == "error" and self.errors.append(f"console: {m.text}"))

    def close(self):
        self.context.close()


@pytest.fixture()
def new_session(browser):
    made: list[Session] = []

    def make(width: int = 1280, height: int = 900) -> Session:
        session = Session(browser, {"width": width, "height": height})
        made.append(session)
        return session

    yield make
    for session in made:
        session.close()


# ── seeding through the API (the parts that are not what a test is about) ────

def call(method: str, path: str, body=None, token: str | None = None, org: str | None = None):
    headers = {"Content-Type": "application/json; charset=utf-8"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if org:
        headers["X-Organization-ID"] = org
    data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
    request = urllib.request.Request(API + path, method=method, headers=headers, data=data)
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


@pytest.fixture()
def shop(stack):
    """A registered owner with a business, a branch and one supplier."""
    tag = uuid.uuid4().hex[:8]
    email = f"owner-{tag}@example.com"
    tokens = call("POST", "/api/app/auth/register",
                  {"email": email, "password": PASSWORD, "display_name": "রহিম উদ্দিন"})
    token = tokens["access_token"]
    org = call("POST", "/api/app/organizations", {
        "name": f"রহিম ফার্মেসি {tag}", "slug": f"rahim-{tag}", "sector": "pharmacy",
        "default_branch_name": "মূল শাখা"}, token)["id"]
    supplier = call("POST", "/api/app/suppliers", {"code": "SUP-1", "name": "Square Distributor"}, token, org)
    return {"email": email, "password": PASSWORD, "token": token, "org": org, "supplier": supplier, "tag": tag}


def bn(value) -> str:
    """Western digits → Bengali digits, as the UI prints them."""
    return str(value).translate(str.maketrans("0123456789", "০১২৩৪৫৬৭৮৯"))


def in_days(days: int) -> str:
    return (date.today() + timedelta(days=days)).isoformat()


def sign_in(session: Session, email: str, password: str = PASSWORD) -> None:
    page = session.page
    page.goto(f"{WEB}/#/login")
    page.get_by_label("ইমেইল").fill(email)
    page.get_by_label("পাসওয়ার্ড").fill(password)
    page.get_by_role("button", name="লগইন", exact=True).click()
    page.locator("main.main").wait_for(state="visible", timeout=20000)  # desktop and phone alike
