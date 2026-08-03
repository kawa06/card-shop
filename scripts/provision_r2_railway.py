"""Provision Cloudflare R2 bucket + S3 credentials and set Railway env vars."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ACCOUNT_ID = "5b536e63c43501107c034ea91f668c0c"
BUCKET_NAME = "krx-buyback-kyc"
BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
WRANGLER_CONFIG = Path.home() / "AppData/Roaming/xdg.config/.wrangler/config/default.toml"


def ensure_wrangler_login() -> None:
    if not WRANGLER_CONFIG.is_file():
        raise RuntimeError("wrangler config not found; run: npx wrangler login")


def run_cmd(args: list[str], *, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    kwargs = {
        "cwd": cwd,
        "capture_output": True,
        "text": True,
        "check": False,
        "encoding": "utf-8",
        "errors": "replace",
    }
    if sys.platform == "win32":
        command = subprocess.list2cmdline(args)
        return subprocess.run(command, shell=True, **kwargs)
    return subprocess.run(args, shell=False, **kwargs)


def ensure_bucket() -> None:
    listed = run_cmd(["npx", "wrangler", "r2", "bucket", "list"])
    if BUCKET_NAME in listed.stdout:
        print(f"bucket: exists ({BUCKET_NAME})")
        return
    created = run_cmd(["npx", "wrangler", "r2", "bucket", "create", BUCKET_NAME])
    if created.returncode != 0:
        combined = (created.stdout or "") + (created.stderr or "")
        if "10042" in combined or "enable R2" in combined:
            raise RuntimeError(
                "Cloudflare R2 is not enabled on this account. "
                "Open the dashboard R2 page, click Get started, and add billing if prompted: "
                f"https://dash.cloudflare.com/{ACCOUNT_ID}/r2/overview"
            )
        raise RuntimeError(combined or "bucket create failed")
    print(f"bucket: created ({BUCKET_NAME})")


def create_r2_s3_credentials() -> tuple[str, str]:
    access_key = __import__("os").environ.get("R2_ACCESS_KEY_ID", "").strip()
    secret_key = __import__("os").environ.get("R2_SECRET_ACCESS_KEY", "").strip()
    if access_key and secret_key:
        print("credentials: using R2_ACCESS_KEY_ID / R2_SECRET_ACCESS_KEY from environment")
        return access_key, secret_key

    raise RuntimeError(
        "Cannot create R2 S3 credentials via wrangler OAuth (Cloudflare returns 403). "
        "After enabling R2, create an API token in the dashboard "
        f"(https://dash.cloudflare.com/{ACCOUNT_ID}/r2/overview -> Manage R2 API Tokens), "
        "then rerun with:\n"
        "  $env:R2_ACCESS_KEY_ID='...'; $env:R2_SECRET_ACCESS_KEY='...'; "
        "python scripts/provision_r2_railway.py"
    )


def set_railway_vars(access_key_id: str, secret_access_key: str) -> None:
    pairs = {
        "R2_ACCOUNT_ID": ACCOUNT_ID,
        "R2_ACCESS_KEY_ID": access_key_id,
        "R2_SECRET_ACCESS_KEY": secret_access_key,
        "R2_BUCKET_NAME": BUCKET_NAME,
    }
    for key, value in pairs.items():
        proc = run_cmd(["railway", "variable", "set", f"{key}={value}", "--skip-deploys"], cwd=BACKEND_DIR)
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr or proc.stdout or f"failed to set {key}")
        print(f"railway: set {key}")
    redeploy = run_cmd(["railway", "up", "--detach"], cwd=BACKEND_DIR)
    if redeploy.returncode != 0:
        raise RuntimeError(redeploy.stderr or redeploy.stdout or "railway up failed")
    print("railway: redeploy triggered")


def main() -> int:
    ensure_wrangler_login()
    ensure_bucket()
    access_key_id, secret_access_key = create_r2_s3_credentials()
    set_railway_vars(access_key_id, secret_access_key)
    print("done")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
