#!/usr/bin/env python3
"""Export buylist Firestore documents to JSON for Phase 8 migration."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

import httpx


def _decode_firestore_value(value: dict) -> Any:
    if "nullValue" in value:
        return None
    if "booleanValue" in value:
        return value["booleanValue"]
    if "integerValue" in value:
        return int(value["integerValue"])
    if "doubleValue" in value:
        return float(value["doubleValue"])
    if "stringValue" in value:
        return value["stringValue"]
    if "timestampValue" in value:
        return value["timestampValue"]
    if "mapValue" in value:
        fields = value["mapValue"].get("fields") or {}
        return {key: _decode_firestore_value(raw) for key, raw in fields.items()}
    if "arrayValue" in value:
        values = value["arrayValue"].get("values") or []
        return [_decode_firestore_value(item) for item in values]
    return None


def load_firebase_config(config_path: Path | None, project_id: str | None, api_key: str | None) -> tuple[str, str]:
    if project_id and api_key:
        return project_id.strip(), api_key.strip()

    if not config_path:
        raise SystemExit("Provide --project-id and --api-key, or --config path to buylist config.js")

    text = config_path.read_text(encoding="utf-8")
    pid_match = re.search(r'projectId:\s*"([^"]+)"', text)
    key_match = re.search(r'apiKey:\s*"([^"]+)"', text)
    if not pid_match or not key_match:
        raise SystemExit(f"Could not parse firebase config from {config_path}")
    return pid_match.group(1), key_match.group(1)


def fetch_document(project_id: str, api_key: str, doc_path: str) -> dict:
    url = (
        f"https://firestore.googleapis.com/v1/projects/{project_id}"
        f"/databases/(default)/documents/{doc_path}?key={api_key}"
    )
    response = httpx.get(url, timeout=60)
    response.raise_for_status()
    payload = response.json()
    fields = payload.get("fields") or {}
    return {key: _decode_firestore_value(raw) for key, raw in fields.items()}


def fetch_image_map(project_id: str, api_key: str) -> dict[str, str]:
    images: dict[str, str] = {}
    page_token: str | None = None
    while True:
        url = (
            f"https://firestore.googleapis.com/v1/projects/{project_id}"
            f"/databases/(default)/documents/product-images?key={api_key}&pageSize=300"
        )
        if page_token:
            url += f"&pageToken={page_token}"
        response = httpx.get(url, timeout=60)
        response.raise_for_status()
        payload = response.json()
        for doc in payload.get("documents") or []:
            name = doc.get("name", "")
            product_id = name.rsplit("/", 1)[-1]
            fields = doc.get("fields") or {}
            data_url = _decode_firestore_value(fields.get("dataUrl", {}))
            if isinstance(data_url, str) and data_url.strip():
                images[product_id] = data_url.strip()
        page_token = payload.get("nextPageToken")
        if not page_token:
            break
    return images


def export_buylist(project_id: str, api_key: str) -> dict:
    main_doc = fetch_document(project_id, api_key, "buylist/main")
    items = main_doc.get("items") or []
    if not isinstance(items, list):
        raise SystemExit("buylist/main.items is missing or not an array")
    images = fetch_image_map(project_id, api_key)
    return {
        "exported_at": __import__("datetime").datetime.utcnow().isoformat() + "Z",
        "project_id": project_id,
        "items": items,
        "images": images,
        "shop": {
            "name": main_doc.get("name"),
            "noticeText": main_doc.get("noticeText"),
            "showNotice": main_doc.get("showNotice"),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Export Firestore buylist to JSON")
    parser.add_argument(
        "--config",
        type=Path,
        default=Path(__file__).resolve().parents[1].parent / "card-vault-buylist" / "config.js",
        help="Path to buylist config.js (default: ../card-vault-buylist/config.js)",
    )
    parser.add_argument("--project-id", default=None)
    parser.add_argument("--api-key", default=None)
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("data/buylist-export.json"),
        help="Output JSON path",
    )
    args = parser.parse_args()

    config_path = args.config if args.config.exists() else None
    project_id, api_key = load_firebase_config(config_path, args.project_id, args.api_key)
    payload = export_buylist(project_id, api_key)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(args.output),
                "item_count": len(payload["items"]),
                "image_count": len(payload["images"]),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
