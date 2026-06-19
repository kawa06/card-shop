import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from database import get_db
from models import TranslationCache
from schemas_translate import TranslateRequest, TranslateResponse
from config import settings

# Translation router (Updated 2026-06-20)
router = APIRouter(tags=["translate"])

DEEPL_API_URL = "https://api-free.deepl.com/v2/translate"


def deepl_translate(texts: List[str], target_lang: str) -> List[str]:
    if not settings.DEEPL_API_KEY:
        raise HTTPException(status_code=503, detail="DeepL API key not configured")

    payload = {
        "text": texts,
        "target_lang": target_lang,
    }
    headers = {
        "Authorization": f"DeepL-Auth-Key {settings.DEEPL_API_KEY}",
        "Content-Type": "application/x-www-form-urlencoded",
    }

    response = httpx.post(
        DEEPL_API_URL,
        data=payload,
        headers=headers,
        timeout=30.0,
    )
    response.raise_for_status()
    result = response.json()
    return [t["text"] for t in result.get("translations", [])]


@router.post("/translate", response_model=TranslateResponse)
def translate(req: TranslateRequest, db: Session = Depends(get_db)):
    if req.target not in ("EN", "JA"):
        raise HTTPException(status_code=400, detail="target must be EN or JA")

    source_lang = "JA" if req.target == "EN" else "EN"
    translations: List[str] = []
    texts_to_translate: List[str] = []
    indices: List[int] = []

    # Check cache first
    for idx, text in enumerate(req.texts):
        if not text or not text.strip():
            translations.append(text)
            continue

        cached = (
            db.query(TranslationCache)
            .filter(
                TranslationCache.source_text == text.strip(),
                TranslationCache.source_lang == source_lang,
                TranslationCache.target_lang == req.target,
            )
            .first()
        )
        if cached:
            translations.append(cached.translated_text)
        else:
            translations.append("")  # placeholder
            texts_to_translate.append(text.strip())
            indices.append(idx)

    # Batch call DeepL if needed
    if texts_to_translate:
        try:
            deepl_results = deepl_translate(texts_to_translate, req.target)
        except Exception:
            # Fallback: return original texts on failure
            deepl_results = texts_to_translate.copy()

        for i, idx in enumerate(indices):
            translated = deepl_results[i]
            original = texts_to_translate[i]
            translations[idx] = translated

            # Save to cache (only on success and if different from original)
            if translated != original:
                try:
                    cache_entry = TranslationCache(
                        source_text=original,
                        source_lang=source_lang,
                        target_lang=req.target,
                        translated_text=translated,
                    )
                    db.add(cache_entry)
                except Exception:
                    pass
        try:
            db.commit()
        except Exception:
            db.rollback()

    return {"translations": translations}
