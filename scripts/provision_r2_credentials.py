"""Create Cloudflare R2 S3 credentials and set Railway env vars (no secrets printed)."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

ACCOUNT_ID = "5b536e63c43501107c034ea91f668c0c"
BUCKET_NAME = "krx-buyback-kyc"
TOKEN_NAME = "krx-buyback-kyc-railway-auto"
BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
CONFIG = Path.home() / "AppData/Roaming/xdg.config/.wrangler/config/default.toml"


def oauth() -> str:
    text = CONFIG.read_text(encoding="utf-8")
    match = re.search(r'oauth_token\s*=\s*"([^"]+)"', text)
    if not match:
        raise RuntimeError("wrangler oauth missing — run: npx wrangler login")
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


def fetch_r2_write_group_id(token: str) -> str:
    scoped_path = (
        f"/accounts/{ACCOUNT_ID}/tokens/permission_groups"
        f"?name=Workers%20R2%20Storage%20Bucket%20Item%20Write"
        f"&scope=com.cloudflare.edge.r2.bucket"
    )
    status, body = api("GET", scoped_path, token)
    if status == 200 and body.get("success"):
        groups = body.get("result") or []
        if groups:
            return groups[0]["id"]

    status, body = api("GET", f"/accounts/{ACCOUNT_ID}/tokens/permission_groups", token)
    if status != 200 or not body.get("success"):
        raise RuntimeError(f"permission_groups failed: {json.dumps(body.get('errors') or body)}")

    group_id = pick_group(body.get("result") or [])
    if not group_id:
        raise RuntimeError("no R2 permission group found")
    return group_id


def normalize_access_key(raw: str) -> str:
    return raw.strip().replace("-", "").lower()


def run_cmd(args: list[str], *, cwd: Path | None = None, input_text: str | None = None) -> None:
    kwargs: dict = {
        "cwd": cwd,
        "capture_output": True,
        "text": True,
        "check": False,
        "encoding": "utf-8",
        "errors": "replace",
    }
    if input_text is not None:
        kwargs["input"] = input_text
    if sys.platform == "win32":
        command = subprocess.list2cmdline(args)
        proc = subprocess.run(command, shell=True, **kwargs)
    else:
        proc = subprocess.run(args, shell=False, **kwargs)
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "command failed").strip()
        raise RuntimeError(detail)


def set_railway_vars(access_key_id: str, secret_access_key: str) -> None:
    run_cmd(
        ["railway", "variable", "set", f"R2_ACCOUNT_ID={ACCOUNT_ID}", "--skip-deploys"],
        cwd=BACKEND_DIR,
    )
    run_cmd(
        ["railway", "variable", "set", f"R2_ACCESS_KEY_ID={access_key_id}", "--skip-deploys"],
        cwd=BACKEND_DIR,
    )
    run_cmd(
        ["railway", "variable", "set", "R2_SECRET_ACCESS_KEY", "--stdin", "--skip-deploys"],
        cwd=BACKEND_DIR,
        input_text=secret_access_key,
    )
    run_cmd(
        ["railway", "variable", "set", f"R2_BUCKET_NAME={BUCKET_NAME}", "--skip-deploys"],
        cwd=BACKEND_DIR,
    )
    run_cmd(["railway", "up", "--detach"], cwd=BACKEND_DIR)


def create_credentials() -> tuple[str, str]:
    """Create Account API token S3 credentials (requires Super Admin)."""
    token = oauth()
    group_id = fetch_r2_write_group_id(token)

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
    if status != 200 or not body.get("success"):
        raise RuntimeError(f"create_token failed: {json.dumps(body.get('errors') or body)}")

    result = body["result"]
    access_key_id = normalize_access_key(result["id"])
    secret_access_key = hashlib.sha256(result["value"].encode("utf-8")).hexdigest()

    if len(access_key_id) != 32:
        raise RuntimeError(f"unexpected access_key_len={len(access_key_id)} (expected 32)")
    if len(secret_access_key) != 64:
        raise RuntimeError(f"unexpected secret_len={len(secret_access_key)} (expected 64)")

    return access_key_id, secret_access_key


def create_user_api_token() -> str:
    """Create a User API token with R2 bucket write (works with wrangler OAuth)."""
    token = oauth()
    group_id = fetch_r2_write_group_id(token)

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
    status, body = api("POST", "/user/tokens", token, payload)
    if status != 200 or not body.get("success"):
        raise RuntimeError(f"create_user_token failed: {json.dumps(body.get('errors') or body)}")

    result = body["result"]
    api_token = result.get("value")
    if not api_token:
        raise RuntimeError("user token value missing from Cloudflare response")
    return api_token


def set_railway_api_token(api_token: str) -> None:
    run_cmd(
        ["railway", "variable", "set", f"R2_ACCOUNT_ID={ACCOUNT_ID}", "--skip-deploys"],
        cwd=BACKEND_DIR,
    )
    run_cmd(
        ["railway", "variable", "set", f"R2_BUCKET_NAME={BUCKET_NAME}", "--skip-deploys"],
        cwd=BACKEND_DIR,
    )
    run_cmd(
        ["railway", "variable", "set", "R2_API_TOKEN", "--stdin", "--skip-deploys"],
        cwd=BACKEND_DIR,
        input_text=api_token,
    )
    run_cmd(["railway", "up", "--detach"], cwd=BACKEND_DIR)


def main() -> int:
    try:
        access_key_id, secret_access_key = create_credentials()
        set_railway_vars(access_key_id, secret_access_key)
        print("OK: R2 S3 credentials created and Railway variables updated")
        print(f"access_key_len={len(access_key_id)} secret_len={len(secret_access_key)} bucket={BUCKET_NAME}")
        return 0
    except RuntimeError as account_err:
        print(f"account token unavailable: {account_err}", file=sys.stderr)
        print("trying user API token + R2 REST API...", file=sys.stderr)

    api_token = create_user_api_token()
    set_railway_api_token(api_token)
    print("OK: R2 user API token created and Railway R2_API_TOKEN updated")
    print(f"token_len={len(api_token)} bucket={BUCKET_NAME}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
