from typing import List
from pydantic import BaseModel


class TranslateRequest(BaseModel):
    texts: List[str]
    target: str  # 'EN' or 'JA'


class TranslateResponse(BaseModel):
    translations: List[str]
