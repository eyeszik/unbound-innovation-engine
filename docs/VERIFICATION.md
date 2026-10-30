# Verification evidence

Verified in the execution workspace on 2026-10-30 with Python 3.12.14. These are actual local checks, not a claim of persistent deployment.

| Check | Result | Evidence |
|---|---|---|
| Dependency installation | PASS | Virtualenv installed from project; `pip check`: no broken requirements |
| Automated suite | PASS | `pytest -q`: **23 passed in 6.77s** |
| GENERAL / VENTURE / HYBRID contract | PASS (mock) | Full graph runs tested for each mode |
| Independent parallel workers | PASS (mock) | Spy provider measured four simultaneous creative calls |
| Counts / all lenses / lineage / ordering | PASS (mock) | Final validation gates and malformed-lineage tests |
| Evaluation isolation | PASS | Generation contexts exclude evidence/scores; evaluation occurs after all synthesis calls |
| Retry / timeout / failure recovery | PASS (mock) | Broken and flaky adapters, timeout tests, phase-preserving retry |
| Persistence and concurrency lease | PASS | SQLite reopening, LangGraph checkpoint retrieval, lease reclaim and competing claimant tests |
| API, errors and exports | PASS | TestClient plus real localhost API/worker run |
| Authentication / CSRF / local-only default | PASS | Unauthorized, bad-password, cross-origin and remote-client tests |
| Optional research adapters | PASS (offline adapter tests) | Missing credentials, simulated retrieval and simulated 401 failure remain honest |
| Phone-width browser workflow | PASS (Chromium emulation) | 390×844, submission, immediate refresh, completed report, history, JSON/Markdown downloads |
| Browser JavaScript errors / overflow | PASS | Zero page errors; document width ≤ viewport width |
| Wheel packaging | PASS | Built wheel; inspected inclusion of HTML, CSS and JavaScript |
| Dependency versions | PASS | Exact installed versions committed in `requirements.lock` |
| Git diff / secret pattern scan | PASS | Whitespace check; no credential-pattern matches in deliverable files |
| Live model inference | NOT_VERIFIED | No configured OpenAI, Anthropic or compatible-provider credentials |
| Live Exa / Wolfram | NOT_VERIFIED | No configured integration credentials; offline tests do not establish live service connectivity |
| Docker/systemd host deployment, TLS, reboot | NOT_VERIFIED | Definitions supplied; no persistent host configured or provisioned |
| Physical iPhone | NOT_VERIFIED | Phone viewport was emulated in Chromium; no actual iPhone session available |
| Repository made private | FAIL | Authenticated integration returned HTTP 403 when changing repository settings |

Final browser run: `2233134c-e103-428f-8f1d-4ad009144b1b`, provider **mock**, model **mock-v1**, status **COMPLETED**. Sixteen structural gates passed: 35 retained raw ideas, 5 wildcards, 5 first-order hybrids, 3 meta-hybrids, 5 finalists, all 12 lenses, valid lineage, evidence-qualified confidence and an execution blueprint. Research was explicitly DISABLED for this deterministic browser check.

Screenshots are local, ignored runtime artifacts: `artifacts/mobile-dashboard.png` and `artifacts/desktop-dashboard.png`. Run outputs persist under ignored `data/`. They are not committed as production evidence or genuine innovation research.

## Reproduce

```bash
pytest -q
playwright install chromium
# Start API and worker in separate terminals with explicit mock environment:
UNBOUND_PROVIDER=mock UNBOUND_MODEL=mock-v1 python -m unbound.worker
UNBOUND_PROVIDER=mock UNBOUND_MODEL=mock-v1 uvicorn unbound.api:app --host 127.0.0.1 --port 8000 --no-proxy-headers
# In another terminal:
python tests/browser_smoke.py
```

Production semantic quality, evidence relevance, speculative claims and harmful-content handling require review with the chosen live model. Structural gates do not establish market truth, real-world feasibility or global uniqueness.

To finish privacy setup, use the repository's **Settings → General → Danger Zone → Change repository visibility → Private** with an account/session permitted to change settings. The connected integration can push application code but cannot perform that setting change.
