import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="session")
def chromium():
    """A real headless browser for the page-map and loop tests. Skipped when
    Playwright has nothing to launch."""
    sync_api = pytest.importorskip("playwright.sync_api")
    driver = sync_api.sync_playwright().start()
    browser = None
    for options in ({}, {"channel": "chrome"}, {"channel": "msedge"}):
        try:
            browser = driver.chromium.launch(**options)
            break
        except Exception:
            continue
    if browser is None:
        driver.stop()
        pytest.skip("Playwright has no Chromium, Chrome or Edge to launch")
    yield browser
    browser.close()
    driver.stop()


@pytest.fixture()
def tab(chromium, monkeypatch):
    """Point the browser tools at a fresh real tab; tab["open"]("feed.html") loads a fixture."""
    from brain.tools import browser as bt
    from brain.tools import ui
    from browser import playwright_controller as pw
    context = chromium.new_context(viewport={"width": 900, "height": 600})
    holder = {"page": context.new_page()}

    def with_page(fn, *args, **kwargs):
        kwargs.pop("call_timeout", None)
        page = holder["page"]
        result = fn(page, *args, **kwargs)
        result.setdefault("url", page.url)
        result.setdefault("title", page.title())
        return result
    monkeypatch.setattr(pw, "with_page", with_page)
    monkeypatch.setattr(pw.controller, "use_tab", lambda page: holder.__setitem__("page", page))
    monkeypatch.setattr(bt, "_on_gmail", lambda page: True)
    monkeypatch.setattr(ui, "_work_window", lambda: None)       # no desktop here: the web channel
    bt._MAP.update(elements={}, groups={})
    holder["open"] = lambda name: holder["page"].goto((FIXTURES / name).as_uri())
    yield holder
    context.close()
