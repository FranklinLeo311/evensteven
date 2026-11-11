"""EvenSteven API: snap a receipt, say who had what, and every friend gets a PayPal link for their exact share."""
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import ai, limits, paypal, store
from .config import get_settings
from .splitting import compute_shares

FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"
MAX_UPLOAD_BYTES = 15 * 1024 * 1024

app = FastAPI(title="EvenSteven")
store.init()


class SplitRequest(BaseModel):
    people: list[str] = Field(min_length=2, max_length=20)
    payer: str
    payee_email: str | None = None
    story: list[str] = []


class CaptureRequest(BaseModel):
    order_id: str


def _bill_or_404(bill_id: str) -> dict:
    bill = store.get_bill(bill_id)
    if not bill:
        raise HTTPException(404, "Bill not found")
    return bill


@app.get("/api/health")
def health():
    """Liveness check used by the host."""
    return {"status": "ok"}


@app.get("/api/config")
def config():
    settings = get_settings()
    return {"paypal_client_id": settings.paypal_client_id, "public_url": settings.public_url,
            "ai_ready": bool(settings.anthropic_api_key), "paypal_ready": bool(settings.paypal_client_id and settings.paypal_client_secret)}


@app.post("/api/bills")
async def create_bill(request: Request, file: UploadFile = File(...)):
    data = await file.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "File is larger than 15 MB")
    limits.check_ai_call(request)
    try:
        receipt = ai.extract_receipt(data, file.content_type or "")
    except ValueError as error:
        raise HTTPException(400, str(error))
    except RuntimeError as error:
        raise HTTPException(502, str(error))
    bill_id = store.create_bill(receipt.model_dump(), paypal.settle_currency(receipt.currency))
    return store.get_bill(bill_id)


@app.get("/api/bills/{bill_id}")
def get_bill(bill_id: str):
    return _bill_or_404(bill_id)


@app.post("/api/bills/{bill_id}/split")
def split_bill(bill_id: str, request: SplitRequest, http_request: Request):
    bill = _bill_or_404(bill_id)
    if any(share["status"] == "paid" for share in bill["shares"]):
        raise HTTPException(409, "Someone has already paid, so the split can't change")
    people = list(dict.fromkeys(name.strip() for name in request.people if name.strip()))
    if request.payer not in people:
        raise HTTPException(400, "The person who paid must be one of the people")
    receipt = ai.Receipt.model_validate(bill["receipt"])
    limits.check_ai_call(http_request)
    try:
        plan = ai.plan_split(receipt, people, request.story)
    except RuntimeError as error:
        raise HTTPException(502, str(error))
    shares = compute_shares(receipt, plan, people)
    store.save_split(bill_id, people, request.payer, (request.payee_email or "").strip() or None, request.story, plan.model_dump(), shares)
    return store.get_bill(bill_id)


@app.get("/api/shares/{share_id}")
def get_share(share_id: str):
    share = store.get_share(share_id)
    if not share:
        raise HTTPException(404, "Share not found")
    bill = store.get_bill(share["bill_id"])
    return {"share": share, "merchant": bill["receipt"]["merchant"], "currency": bill["currency"], "payer": bill["payer"]}


@app.post("/api/shares/{share_id}/order")
def create_order(share_id: str):
    share = store.get_share(share_id)
    if not share or share["status"] != "pending":
        raise HTTPException(409, "This share is not waiting for payment")
    bill = store.get_bill(share["bill_id"])
    description = f"{share['person']}'s share at {bill['receipt']['merchant']} (paid by {bill['payer']})"
    try:
        order = paypal.create_order(share_id, share["amount"], bill["currency"], description, bill["payee_email"])
    except paypal.PayPalError as error:
        raise HTTPException(502, str(error))
    store.set_order(share_id, order["id"])
    return {"order_id": order["id"]}


@app.post("/api/shares/{share_id}/capture")
def capture_order(share_id: str, request: CaptureRequest):
    share = store.get_share(share_id)
    if not share or share["order_id"] != request.order_id:
        raise HTTPException(409, "This order doesn't belong to this share")
    if share["status"] == "paid":
        return {"status": "paid"}
    try:
        result = paypal.capture_order(request.order_id)
    except paypal.PayPalError as error:
        raise HTTPException(502, str(error))
    capture = result["purchase_units"][0]["payments"]["captures"][0]
    if capture["status"] not in ("COMPLETED", "PENDING"):
        raise HTTPException(402, f"Payment was not completed ({capture['status']})")
    store.mark_paid(share_id, capture["id"])
    return {"status": "paid", "capture_id": capture["id"]}


# the built React app; any non-API path falls through to index.html so client routes like /pay/<id> work
if FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

    @app.get("/{path:path}")
    def spa(path: str):
        file = (FRONTEND_DIST / path).resolve()
        inside = file.is_relative_to(FRONTEND_DIST.resolve())
        return FileResponse(file if path and inside and file.is_file() else FRONTEND_DIST / "index.html")
