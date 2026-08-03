"""Apply Resend DNS records to Cloudflare using local wrangler OAuth."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
CONFIG = Path.home() / "AppData/Roaming/xdg.config/.wrangler/config/default.toml"


def oauth_token() -> str:
    text = CONFIG.read_text(encoding="utf-8")
    match = re.search(r'oauth_token\s*=\s*"([^"]+)"', text)
    if not match:
        raise RuntimeError("wrangler oauth missing — run: npx wrangler login")
    return match.group(1)


def run_cmd(args: list[str], *, cwd: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    kwargs: dict = {
        "cwd": cwd,
        "env": env,
        "text": True,
        "capture_output": True,
    }
    if sys.platform == "win32":
        return subprocess.run(subprocess.list2cmdline(args), shell=True, **kwargs)
    return subprocess.run(args, shell=False, **kwargs)


def main() -> int:
    token = oauth_token()
    proc = run_cmd(
        ["railway", "run", "python", "scripts/provision_resend_dns_cloudflare.py"],
        cwd=BACKEND,
        env={**dict(__import__("os").environ), "CLOUDFLARE_API_TOKEN": token},
    )
    if proc.stdout:
        print(proc.stdout.strip())
    if proc.returncode != 0:
        if proc.stderr:
            print(proc.stderr.strip(), file=sys.stderr)
        print(
            "\nIf DNS write failed (403), create a Cloudflare API token with "
            "Zone.DNS Edit for oripa-kawa.com and run:\n"
            "  set CLOUDFLARE_API_TOKEN=... && railway run python scripts/provision_resend_dns_cloudflare.py",
            file=sys.stderr,
        )
        return proc.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
