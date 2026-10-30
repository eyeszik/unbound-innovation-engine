"""Run against an explicitly configured mock API + worker: python tests/browser_smoke.py."""

import json
import re
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

URL = "http://127.0.0.1:8000"
Path("artifacts").mkdir(exist_ok=True)
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
    page = browser.new_page(
        viewport={"width": 390, "height": 844}, device_scale_factor=1
    )
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(URL)
    page.get_by_text("OFFLINE MOCK MODE", exact=False).wait_for()
    page.locator("#input").fill(
        "Explore unconventional ways to share neighborhood library capabilities"
    )
    page.locator("#research").select_option("DISABLED")
    page.get_by_role("button", name="Start Run").click()
    page.wait_for_url("**/?run=*")
    run_id = page.url.split("run=")[1]
    page.reload()  # Reconnect from the URL immediately after submission.
    expect(page.locator("#run-meta")).to_have_text(
        re.compile(r"^COMPLETED"), timeout=60000
    )
    page.reload()
    expect(page.locator("#run-meta")).to_have_text(
        re.compile(r"^COMPLETED"), timeout=10000
    )
    assert page.locator("#workers").inner_text().count("COMPLETED") == 4
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    report = page.request.get(f"{URL}/runs/{run_id}/export.json").json()
    assert report["outputs"]["OUTPUT_VALIDATED"]["passed"]
    assert report["outputs"]["OUTPUT_VALIDATED"]["raw_count"] == 35
    md = page.request.get(f"{URL}/runs/{run_id}/export.md").text()
    assert all(mark in md for mark in ["①", "②", "③", "④", "⑤", "⑥", "⑦", "⑧", "⑨"])
    for button, filename in [
        ("json", "innovation-report.json"),
        ("md", "innovation-report.md"),
    ]:
        with page.expect_download() as download:
            page.locator("#" + button).click()
        assert download.value.suggested_filename == filename
    assert not errors, errors
    page.screenshot(path="artifacts/mobile-dashboard.png", full_page=True)
    page.set_viewport_size({"width": 1440, "height": 1000})
    page.screenshot(path="artifacts/desktop-dashboard.png", full_page=True)
    print(
        json.dumps(
            {
                "run_id": run_id,
                "status": report["status"],
                "provider": report["provider"],
                "validation": report["outputs"]["OUTPUT_VALIDATED"],
                "browser_errors": errors,
                "mobile_horizontal_overflow": False,
            },
            indent=2,
        )
    )
    browser.close()
