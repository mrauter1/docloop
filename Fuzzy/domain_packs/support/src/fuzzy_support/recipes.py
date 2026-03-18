from __future__ import annotations


def support_triage_recipe(payload: dict[str, object]) -> dict[str, object]:
    return {"pack": "support", "received": payload}
