"""Set Railway R2_API_TOKEN from local wrangler OAuth (no secrets printed)."""

from __future__ import annotations

import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

ACCOUNT_ID = "5b536e63c43501107c034ea91f668c0c"
BUCKET_NAME = "krx-buyback-kyc"
BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
CONFIG = Path.home() / "AppData/Roaming/xdg.config/.wrangler/config/default.toml"

PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01"
    b"\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)


def oauth() -> str:
    text = CONFIG.read_text(encoding="utf-8")
    match = re.search(r'oauth_token\s*=\s*"([^"]+)"', text)
    if not match:
        raise RuntimeError("wrangler oauth missing — run: npx wrangler login")
    return match.group(1)


def test_upload(token: str) -> None:
    key = "diag/railway-token-probe.png"
    url = (
        f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}"
        f"/r2/buckets/{BUCKET_NAME}/objects/{key}"
    )
    req = urllib.request.Request(
        url,
        data=PNG,
        method="PUT",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "image/png",
        },
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        if resp.status >= 400:
            raise RuntimeError(f"upload probe failed status={resp.status}")


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
        proc = subprocess.run(subprocess.list2cmdline(args), shell=True, **kwargs)
    else:
        proc = subprocess.run(args, shell=False, **kwargs)
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout or "command failed").strip())


def main() -> int:
    token = oauth()
    test_upload(token)
    run_cmd(["railway", "variable", "set", f"R2_ACCOUNT_ID={ACCOUNT_ID}", "--skip-deploys"], cwd=BACKEND_DIR)
    run_cmd(["railway", "variable", "set", f"R2_BUCKET_NAME={BUCKET_NAME}", "--skip-deploys"], cwd=BACKEND_DIR)
    run_cmd(
        ["railway", "variable", "set", "R2_API_TOKEN", "--stdin", "--skip-deploys"],
        cwd=BACKEND_DIR,
        input_text=token,
    )
    run_cmd(["railway", "up", "--detach"], cwd=BACKEND_DIR)
    print("OK: wrangler OAuth verified for R2 REST upload; Railway R2_API_TOKEN updated")
    print(f"token_len={len(token)} bucket={BUCKET_NAME}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
