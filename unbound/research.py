import os
import httpx
from .store import now


async def research(input_text, mode, setting):
    if setting == "DISABLED":
        return {
            "status": "DISABLED",
            "evidence": [],
            "questions": [
                "Which essential claims and analogous offerings need independent validation?"
            ],
        }
    key = os.getenv("EXA_API_KEY")
    evidence = []
    if key:
        async with httpx.AsyncClient(timeout=25) as client:
            for kind in (
                "analogous offerings and competitors",
                "technology capabilities and limitations",
            ):
                try:
                    response = await client.post(
                        "https://api.exa.ai/search",
                        headers={"x-api-key": key},
                        json={
                            "query": f"{input_text[:1000]} {kind}",
                            "numResults": 5,
                            "contents": {"text": {"maxCharacters": 1600}},
                        },
                    )
                    response.raise_for_status()
                    for item in response.json().get("results", []):
                        url = item.get("url", "")
                        if not url.startswith(("https://", "http://")):
                            continue
                        evidence.append(
                            {
                                "id": f"E{len(evidence) + 1:02}",
                                "claim": item.get("title", "Retrieved source"),
                                "url": url,
                                "retrieved_at": now(),
                                "status": "RETRIEVED",
                                "excerpt": item.get("text", "")[:1600],
                                "limitations": "Search retrieval is not independent verification of the source claim.",
                            }
                        )
                except (httpx.HTTPError, ValueError):
                    evidence.append(
                        {
                            "id": f"E{len(evidence) + 1:02}",
                            "claim": kind,
                            "url": None,
                            "retrieved_at": now(),
                            "status": "UNVERIFIED",
                            "excerpt": "",
                            "limitations": "Exa request failed; check configured credentials, quota and connectivity.",
                        }
                    )
    available = any(e["status"] == "RETRIEVED" for e in evidence)
    return {
        "status": "RETRIEVED" if available else "UNAVAILABLE",
        "evidence": evidence,
        "questions": [
            "What existing offerings implement the same mechanism?",
            "Which essential technology assumptions survive an independent test?",
            "What measured buyer demand supports commercial claims?",
        ]
        if mode != "GENERAL"
        else [
            "Which analogues exist?",
            "Which defining mechanism needs a controlled test?",
        ],
        "limitations": [
            "No search result is proof of global novelty.",
            "Unretrieved claims remain unverified.",
        ],
    }


async def compute(query):
    """Optional Wolfram computation adapter; invoked only for explicit numeric questions."""
    appid = os.getenv("WOLFRAM_APP_ID")
    if not appid:
        return {"status": "UNAVAILABLE", "result": None}
    try:
        async with httpx.AsyncClient(timeout=25) as client:
            r = await client.get(
                "https://api.wolframalpha.com/v2/query",
                params={
                    "appid": appid,
                    "input": query,
                    "output": "json",
                    "format": "plaintext",
                },
            )
            r.raise_for_status()
            data = r.json()["queryresult"]
            texts = [
                s.get("plaintext", "")
                for p in data.get("pods", [])
                for s in p.get("subpods", [])
            ]
            return {
                "status": "COMPUTED" if data.get("success") else "UNVERIFIED",
                "result": texts,
                "limitations": "Computation validates supplied assumptions, not their empirical truth.",
            }
    except (httpx.HTTPError, ValueError, KeyError):
        return {
            "status": "UNVERIFIED",
            "result": None,
            "limitations": "Wolfram request failed; check credentials, quota and connectivity.",
        }
