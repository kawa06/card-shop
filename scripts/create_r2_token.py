"""Try to create a new R2-scoped account token via Cloudflare API (wrangler OAuth)."""

from __future__ import annotations

import hashlib
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

ACCOUNT_ID = "5b536e63c43501107c034ea91f668c0c"
BUCKET_NAME = "krx-buyback-kyc"
TOKEN_NAME = "krx-buyback-kyc-railway-auto"
CONFIG = Path.home() / "AppData/Roaming/xdg.config/.wrangler/config/default.toml"


def oauth() -> str:
    text = CONFIG.read_text(encoding="utf-8")
    match = re.search(r'oauth_token\s*=\s*"([^"]+)"', text)
    if not match:
        raise RuntimeError("wrangler oauth missing")
    return match.group(1)


def api(method: str, path: str, token: str, payload: dict | None = None) -> tuple[int, dict]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"https://api.cloudflare.com/client/v4{path}",
        data=data,
        method=method,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(body)
        except json.JSONDecodeError:
            parsed = {"raw": body}
        return exc.code, parsed


def pick_group(groups: list[dict]) -> str | None:
    for name in (
        "Workers R2 Storage Bucket Item Write",
        "Workers R2 Storage Write",
        "Workers R2 Storage Bucket Item Read",
    ):
        for group in groups:
            if group.get("name") == name:
                return group["id"]
    return None


def main() -> int:
    token = oauth()
    status, body = api("GET", f"/accounts/{ACCOUNT_ID}/tokens/permission_groups", token)
    print(f"permission_groups: {status}")
    if status != 200 or not body.get("success"):
        print(json.dumps(body.get("errors") or body, ensure_ascii=False))
        return 1

    group_id = pick_group(body.get("result") or [])
    if not group_id:
        print("no R2 permission group found")
        return 1

    resource_key = f"com.cloudflare.edge.r2.bucket.{ACCOUNT_ID}_default_{BUCKET_NAME}"
    payload = {
        "name": TOKEN_NAME,
        "policies": [
            {
                "effect": "allow",
                "resources": {resource_key: "*"},
                "permission_groups": [{"id": group_id}],
            }
        ],
    }
    status, body = api("POST", f"/accounts/{ACCOUNT_ID}/tokens", token, payload)
    print(f"create_token: {status}")
    if status != 200 or not body.get("success"):
        print(json.dumps(body.get("errors") or body, ensure_ascii=False))
        return 1

    result = body["result"]
    access_key_id = result["id"]
    secret = hashlib.sha256(result["value"].encode("utf-8")).hexdigest()
    print("created=yes")
    print(f"access_key_id_len={len(access_key_id)}")
    print(f"secret_len={len(secret)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
