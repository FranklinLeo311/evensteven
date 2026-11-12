"""AI calls: read a receipt photo or PDF, and work out who had what from how the group describes the meal.

Two providers give the same typed results: Claude (Anthropic SDK, structured outputs) and Gemini (REST, JSON schema).
AI_PROVIDER picks one; "auto" uses Claude when its key is set, otherwise Gemini.
"""
import base64
import copy
import io
import json
import time

import anthropic
import httpx
from PIL import Image
from pydantic import BaseModel, Field

from .config import get_settings

IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
# long side in pixels; bigger photos only cost more tokens without reading better
MAX_IMAGE_SIDE = 1600


class ReceiptItem(BaseModel):
    name: str = Field(description="Item name as printed, cleaned up to be readable")
    quantity: float = Field(description="Quantity, 1 when not printed")
    line_total: float = Field(description="Price of the whole line (quantity x unit price), after any line discount")


class Receipt(BaseModel):
    merchant: str
    currency: str = Field(description="ISO 4217 code, e.g. USD, INR, EUR; infer from symbols and address")
    items: list[ReceiptItem]
    tax: float = Field(description="All taxes and service charges added on top of the items; 0 when none")
    tip: float = Field(description="Tip or gratuity printed on the receipt; 0 when none")
    total: float = Field(description="Grand total the payer was charged")
    warnings: list[str] = Field(description="Anything that looks off: unreadable lines, totals that don't add up, discounts")


class Portion(BaseModel):
    person: str = Field(description="Exactly one of the given names")
    weight: float = Field(description="Relative share of the item; equal sharing means weight 1 for each person")


class ItemAssignment(BaseModel):
    item_index: int
    portions: list[Portion]
    reason: str = Field(description="Short reason, quoting the story when possible")


class PersonNote(BaseModel):
    person: str
    note: str = Field(description="One friendly, playful line for this person's payment request, mentioning what they had")


class SplitPlan(BaseModel):
    assignments: list[ItemAssignment]
    tip_override: float | None = Field(description="Tip amount only when the story asks for a tip the receipt doesn't show; otherwise null")
    notes: list[PersonNote]
    questions: list[str] = Field(description="Real ambiguities the group should confirm; empty when everything is clear")
    summary: str = Field(description="Two sentences on how the bill was split")


EXTRACT_PROMPT = """Read this receipt and return its line items and totals.
Use the printed numbers; do not invent items. Leave out subtotal, tax, tip and total lines from items.
If tax or service is printed, put the sum of them in tax. Check that items + tax + tip is close to the total and add a warning if not."""

SPLIT_SYSTEM = """You split restaurant and shop bills between friends.
You get the receipt items (with their index), the names of the people, and what the group said about who had what.
Assign every item. Shared items go to everyone who shared them; items nobody is mentioned for are shared by everyone, and say so in the reason.
Use weights for uneven shares ("Sam had two of the three beers" -> Sam 2, other drinker 1).
Later instructions in the story override earlier ones.
Only use the given names, spelled exactly as given."""


GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


def provider() -> str:
    """The AI provider in use: 'claude', 'gemini', or '' when no key is set."""
    settings = get_settings()
    choice = settings.ai_provider.strip().lower()
    if choice in ("claude", "gemini"):
        return choice
    if settings.anthropic_api_key:
        return "claude"
    return "gemini" if settings.gemini_api_key else ""


def is_ready() -> bool:
    """True when the chosen provider has its key."""
    settings = get_settings()
    return {"claude": bool(settings.anthropic_api_key), "gemini": bool(settings.gemini_api_key)}.get(provider(), False)


def _client() -> anthropic.Anthropic:
    settings = get_settings()
    if not settings.anthropic_api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set (backend/.env locally, or the host's environment variables)")
    return anthropic.Anthropic(api_key=settings.anthropic_api_key)


def _scaled_image(data: bytes, media_type: str) -> tuple[bytes, str]:
    """Large photos scaled down to MAX_IMAGE_SIDE; other files unchanged."""
    if media_type == "application/pdf":
        return data, media_type
    if media_type not in IMAGE_TYPES:
        raise ValueError(f"Unsupported file type {media_type}; use a JPG, PNG, WEBP or PDF")
    image = Image.open(io.BytesIO(data))
    if max(image.size) > MAX_IMAGE_SIDE:
        image.thumbnail((MAX_IMAGE_SIDE, MAX_IMAGE_SIDE))
        buffer = io.BytesIO()
        image.convert("RGB").save(buffer, format="JPEG", quality=90)
        data, media_type = buffer.getvalue(), "image/jpeg"
    return data, media_type


def _file_block(data: bytes, media_type: str) -> dict:
    """Claude image or PDF content block."""
    data, media_type = _scaled_image(data, media_type)
    block_type = "document" if media_type == "application/pdf" else "image"
    return {"type": block_type, "source": {"type": "base64", "media_type": media_type, "data": base64.b64encode(data).decode()}}


def _gemini_schema(model: type[BaseModel]) -> dict:
    """Pydantic JSON schema with $refs inlined and titles dropped, the shape Gemini's responseJsonSchema accepts."""
    schema = model.model_json_schema()
    definitions = schema.pop("$defs", {})

    def inline(node):
        if isinstance(node, dict):
            if "$ref" in node:
                return inline(copy.deepcopy(definitions[node["$ref"].split("/")[-1]]))
            return {key: inline(value) for key, value in node.items() if key not in ("title", "default")}
        if isinstance(node, list):
            return [inline(value) for value in node]
        return node

    return inline(schema)


def _gemini(parts: list[dict], output: type[BaseModel], system: str | None = None) -> BaseModel:
    """One Gemini call that must return JSON matching the output model."""
    settings = get_settings()
    if not settings.gemini_api_key:
        raise RuntimeError("GEMINI_API_KEY is not set (backend/.env locally, or the host's environment variables)")
    body = {"contents": [{"role": "user", "parts": parts}],
            "generationConfig": {"responseMimeType": "application/json", "responseJsonSchema": _gemini_schema(output), "temperature": 0.2}}
    if system:
        body["systemInstruction"] = {"parts": [{"text": system}]}
    # GEMINI_MODEL may list fallbacks ("a,b,c"): free models are often busy (503), so retry, then move to the next one
    response = None
    for model in [name.strip() for name in settings.gemini_model.split(",") if name.strip()]:
        for attempt in range(2):
            response = httpx.post(GEMINI_URL.format(model=model), json=body, timeout=120,
                                  headers={"x-goog-api-key": settings.gemini_api_key})
            if response.status_code not in (429, 500, 503):
                break
            time.sleep(2 + attempt * 3)
        if response.status_code == 200:
            break
    if response is None:
        raise RuntimeError("GEMINI_MODEL is empty")
    if response.status_code in (429, 503):
        raise RuntimeError("The free AI is busy right now; please try again in a minute")
    if response.status_code != 200:
        raise RuntimeError(f"The AI call failed ({response.status_code}): {response.text[:200]}")
    candidates = response.json().get("candidates") or []
    text = "".join(part.get("text", "") for part in (candidates[0].get("content", {}).get("parts", []) if candidates else [])
                   if not part.get("thought"))
    if not text:
        raise RuntimeError("The AI returned no answer")
    return output.model_validate(json.loads(text))


def extract_receipt(data: bytes, media_type: str) -> Receipt:
    if provider() == "gemini":
        data, media_type = _scaled_image(data, media_type)
        file_part = {"inline_data": {"mime_type": media_type, "data": base64.b64encode(data).decode()}}
        return _gemini([file_part, {"text": EXTRACT_PROMPT}], Receipt)
    response = _client().messages.parse(
        model=get_settings().claude_model,
        max_tokens=16000,
        messages=[{"role": "user", "content": [_file_block(data, media_type), {"type": "text", "text": EXTRACT_PROMPT}]}],
        output_format=Receipt,
    )
    if response.stop_reason == "refusal" or response.parsed_output is None:
        raise RuntimeError("The receipt could not be read")
    return response.parsed_output


def plan_split(receipt: Receipt, people: list[str], story: list[str]) -> SplitPlan:
    items = "\n".join(f"[{index}] {item.name} x{item.quantity:g} = {item.line_total:.2f}" for index, item in enumerate(receipt.items))
    said = "\n".join(f"- {line}" for line in story) or "- (nothing said; share everything equally)"
    content = (f"Receipt from {receipt.merchant} ({receipt.currency}), tax {receipt.tax:.2f}, tip {receipt.tip:.2f}:\n{items}\n\n"
               f"People: {', '.join(people)}\n\nWhat the group said, oldest first:\n{said}")
    if provider() == "gemini":
        return _gemini([{"text": content}], SplitPlan, system=SPLIT_SYSTEM)
    response = _client().messages.parse(
        model=get_settings().claude_model,
        max_tokens=16000,
        system=SPLIT_SYSTEM,
        messages=[{"role": "user", "content": content}],
        output_format=SplitPlan,
    )
    if response.stop_reason == "refusal" or response.parsed_output is None:
        raise RuntimeError("The split could not be worked out")
    return response.parsed_output
