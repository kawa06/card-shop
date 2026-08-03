#!/usr/bin/env python3
"""Upsert Resend DNS records in Cloudflare for oripa-kawa.com."""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx

from config import settings

TARGET_DOMAIN = "oripa-kawa.com"
CF_API = "https://api.cloudflare.com/client/v4"


def _cf_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def _zone_id(client: httpx.Client, token: str, domain: str) -> str:
    resp = client.get(
        f"{CF_API}/zones",
        headers=_cf_headers(token),
        params={"name": domain, "status": "active"},
    )
    resp.raise_for_status()
    rows = resp.json().get("result") or []
    if not rows:
        raise RuntimeError(f"Cloudflare zone not found for {domain}")
    return rows[0]["id"]


def _upsert_record(
    client: httpx.Client,
    token: str,
    zone_id: str,
    *,
    rtype: str,
    name: str,
    content: str,
    priority: int | None = None,
) -> None:
    fqdn = name if name.endswith(f".{TARGET_DOMAIN}") or name == TARGET_DOMAIN else f"{name}.{TARGET_DOMAIN}"
    if name == "send":
        fqdn = f"send.{TARGET_DOMAIN}"
    elif name.startswith("resend._domainkey"):
        fqdn = f"resend._domainkey.{TARGET_DOMAIN}"

    list_resp = client.get(
        f"{CF_API}/zones/{zone_id}/dns_records",
        headers=_cf_headers(token),
        params={"type": rtype, "name": fqdn},
    )
    list_resp.raise_for_status()
    existing = list_resp.json().get("result") or []

    payload: dict = {"type": rtype, "name": fqdn, "content": content, "ttl": 3600}
    if rtype == "MX" and priority is not None:
        payload["priority"] = priority

    if existing:
        rec_id = existing[0]["id"]
        resp = client.put(
            f"{CF_API}/zones/{zone_id}/dns_records/{rec_id}",
            headers=_cf_headers(token),
            json=payload,
        )
        action = "updated"
    else:
        resp = client.post(
            f"{CF_API}/zones/{zone_id}/dns_records",
            headers=_cf_headers(token),
            json=payload,
        )
        action = "created"

    if resp.status_code >= 400:
        raise RuntimeError(f"Failed to {action} {rtype} {fqdn}: {resp.status_code} {resp.text}")
    print(f"{action}: {rtype} {fqdn}")


def main() -> int:
    cf_token = os.environ.get("CLOUDFLARE_API_TOKEN", "").strip()
    if not cf_token:
        print("Set CLOUDFLARE_API_TOKEN with Zone.DNS Edit for oripa-kawa.com", file=sys.stderr)
        return 1

    resend_key = settings.RESEND_API_KEY or os.environ.get("RESEND_API_KEY")
    if not resend_key:
        print("RESEND_API_KEY is not configured", file=sys.stderr)
        return 1

    headers = {"Authorization": f"Bearer {resend_key}"}
    with httpx.Client(timeout=30.0) as client:
        list_resp = client.get("https://api.resend.com/domains", headers=headers)
        list_resp.raise_for_status()
        target = next(
            (d for d in list_resp.json().get("data") or [] if d.get("name") == TARGET_DOMAIN),
            None,
        )
        if not target:
            print(f"Domain {TARGET_DOMAIN} not found in Resend", file=sys.stderr)
            return 1

        detail = client.get(f"https://api.resend.com/domains/{target['id']}", headers=headers)
        detail.raise_for_status()
        records = detail.json().get("records") or []
        if not records:
            print("No DNS records from Resend", file=sys.stderr)
            return 1

        zone_id = _zone_id(client, cf_token, TARGET_DOMAIN)
        print(f"Cloudflare zone: {TARGET_DOMAIN} ({zone_id})")

        for rec in records:
            rtype = rec.get("type") or rec.get("record")
            name = rec.get("name") or ""
            value = rec.get("value") or rec.get("content")
            priority = rec.get("priority")
            if not rtype or not value:
                continue
            _upsert_record(
                client,
                cf_token,
                zone_id,
                rtype=rtype,
                name=name,
                content=value,
                priority=priority,
            )

        verify = client.post(f"https://api.resend.com/domains/{target['id']}/verify", headers=headers)
        print(f"Resend verify: {verify.status_code}")
        refreshed = client.get(f"https://api.resend.com/domains/{target['id']}", headers=headers)
        if refreshed.status_code == 200:
            print(f"Resend status: {refreshed.json().get('status')}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
