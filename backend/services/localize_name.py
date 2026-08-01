"""Fill English display names for categories / packs via DeepL + DB cache."""

from __future__ import annotations

import logging
from typing import Iterable, List, Optional, Sequence

import httpx
from sqlalchemy.orm import Session

from config import settings
from models import TranslationCache

logger = logging.getLogger(__name__)

DEEPL_API_URL = "https://api-free.deepl.com/v2/translate"

# Prefer stable shop catalog English over machine translation.
CATALOG_NAME_EN = {
    "ポケモンカード": "Pokémon Cards",
    "ワンピースカード": "One Piece Cards",
    "メガドリームex": "Mega Dream ex",
}


def _deepl_translate(texts: List[str], target_lang: str = "EN") -> List[str]:
    if not settings.DEEPL_API_KEY:
        raise RuntimeError("DeepL API key not configured")
    response = httpx.post(
        DEEPL_API_URL,
        data=[("text", t) for t in texts] + [("target_lang", target_lang)],
        headers={"Authorization": f"DeepL-Auth-Key {settings.DEEPL_API_KEY}"},
        timeout=30.0,
    )
    response.raise_for_status()
    result = response.json()
    return [row["text"] for row in result.get("translations", [])]


def _mymemory_translate(text: str) -> Optional[str]:
    """Free fallback when DeepL is unavailable (rate-limited)."""
    try:
        response = httpx.get(
            "https://api.mymemory.translated.net/get",
            params={"q": text, "langpair": "ja|en"},
            timeout=20.0,
        )
        response.raise_for_status()
        data = response.json()
        translated = (
            (data.get("responseData") or {}).get("translatedText")
            or ""
        ).strip()
        if not translated:
            return None
        # MyMemory returns the source when it fails / rejects.
        if translated.casefold() == text.casefold():
            return None
        return translated
    except Exception:
        logger.warning("MyMemory translate failed")
        return None


def translate_external_batch(texts: List[str]) -> List[Optional[str]]:
    """Translate Japanese texts to English using DeepL or the free fallback."""
    if not texts:
        return []
    if settings.DEEPL_API_KEY:
        try:
            return list(_deepl_translate(texts, "EN"))
        except Exception:
            logger.warning("DeepL translate failed, falling back")
    return [_mymemory_translate(t) for t in texts]


def translate_ja_to_en(db: Session, texts: Sequence[str]) -> List[Optional[str]]:
    """Return EN strings aligned with input; None when translation unavailable."""
    out: List[Optional[str]] = [None] * len(texts)
    if not texts:
        return out

    missed: List[tuple[int, str]] = []
    for idx, raw in enumerate(texts):
        text = (raw or "").strip()
        if not text:
            continue
        catalog = CATALOG_NAME_EN.get(text)
        if catalog:
            out[idx] = catalog
            continue
        # Already Latin-only (e.g. "Mega Dream ex") — reuse as English.
        if all(ord(c) < 128 for c in text):
            out[idx] = text
            continue
        cached = (
            db.query(TranslationCache)
            .filter(
                TranslationCache.source_text == text,
                TranslationCache.source_lang == "JA",
                TranslationCache.target_lang == "EN",
            )
            .first()
        )
        if cached and cached.translated_text:
            out[idx] = cached.translated_text
        else:
            missed.append((idx, text))

    if not missed:
        return out

    try:
        translated = translate_external_batch([t for _, t in missed])
    except Exception:
        logger.warning("Catalog name translate failed")
        return out

    for i, (idx, original) in enumerate(missed):
        value = translated[i] if i < len(translated) else None
        if not value:
            continue
        out[idx] = value
        if value != original:
            try:
                db.add(
                    TranslationCache(
                        source_text=original,
                        source_lang="JA",
                        target_lang="EN",
                        translated_text=value,
                    )
                )
            except Exception:
                pass
    try:
        db.commit()
    except Exception:
        db.rollback()
    return out


def fill_name_en(db: Session, name: str, name_en: Optional[str]) -> Optional[str]:
    """Prefer explicit name_en; otherwise translate Japanese name."""
    if name_en and name_en.strip():
        return name_en.strip()
    results = translate_ja_to_en(db, [name or ""])
    return results[0] if results else None


def backfill_name_en_fields(db: Session, rows: Iterable[object]) -> int:
    """Persist missing (or catalog-corrected) name_en on model rows."""
    rows = [row for row in rows if row is not None]
    if not rows:
        return 0

    updated = 0
    # Always enforce known catalog English labels.
    for row in rows:
        name = getattr(row, "name", "") or ""
        catalog = CATALOG_NAME_EN.get(name)
        if catalog and (getattr(row, "name_en", None) or "").strip() != catalog:
            row.name_en = catalog
            updated += 1

    targets = [
        row
        for row in rows
        if not (getattr(row, "name_en", None) or "").strip()
    ]
    if targets:
        names = [getattr(row, "name", "") or "" for row in targets]
        translated = translate_ja_to_en(db, names)
        for row, en in zip(targets, translated):
            if en:
                row.name_en = en
                updated += 1

    if updated:
        try:
            db.commit()
        except Exception:
            db.rollback()
            return 0
    return updated
