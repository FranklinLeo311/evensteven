"""Claude calls: read a receipt photo or PDF, and work out who had what from how the group describes the meal."""
import base64
import io

import anthropic
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


def _client() -> anthropic.Anthropic:
    settings = get_settings()
    if not settings.anthropic_api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set (backend/.env locally, or the host's environment variables)")
    return anthropic.Anthropic(api_key=settings.anthropic_api_key)


def _file_block(data: bytes, media_type: str) -> dict:
    """Image or PDF content block; large photos are scaled down first."""
    if media_type == "application/pdf":
        return {"type": "document", "source": {"type": "base64", "media_type": media_type, "data": base64.b64encode(data).decode()}}
    if media_type not in IMAGE_TYPES:
        raise ValueError(f"Unsupported file type {media_type}; use a JPG, PNG, WEBP or PDF")
    image = Image.open(io.BytesIO(data))
    if max(image.size) > MAX_IMAGE_SIDE:
        image.thumbnail((MAX_IMAGE_SIDE, MAX_IMAGE_SIDE))
        buffer = io.BytesIO()
        image.convert("RGB").save(buffer, format="JPEG", quality=90)
        data, media_type = buffer.getvalue(), "image/jpeg"
    return {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": base64.b64encode(data).decode()}}


def extract_receipt(data: bytes, media_type: str) -> Receipt:
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
