"""Turn the AI's item assignments into exact per-person amounts that add up to the receipt total, to the cent."""
from .ai import Receipt, SplitPlan


def compute_shares(receipt: Receipt, plan: SplitPlan, people: list[str]) -> list[dict]:
    """Each person's items, item subtotal, share of tax/tip/discounts and total (in cents, summing to the bill total).
    The whole bill is spread in proportion to item subtotals, so tax, tip and discounts fall where the food did."""
    known = {name.casefold(): name for name in people}
    lines = {name: [] for name in people}
    item_totals = {name: 0.0 for name in people}
    assigned = set()
    for assignment in plan.assignments:
        if not 0 <= assignment.item_index < len(receipt.items) or assignment.item_index in assigned:
            continue
        portions = [(known[p.person.casefold()], p.weight) for p in assignment.portions if p.person.casefold() in known and p.weight > 0]
        if not portions:
            continue
        assigned.add(assignment.item_index)
        _spread(receipt.items[assignment.item_index], portions, lines, item_totals, assignment.reason)
    # anything the AI missed is shared by everyone, so the totals still add up
    for index, item in enumerate(receipt.items):
        if index not in assigned:
            _spread(item, [(name, 1.0) for name in people], lines, item_totals, "Not mentioned, so shared by everyone")

    tip_extra = plan.tip_override if plan.tip_override and receipt.tip == 0 else 0.0
    bill_cents = round((receipt.total + tip_extra) * 100)
    items_sum = sum(item_totals.values())
    raw = {name: bill_cents * item_totals[name] / items_sum if items_sum else bill_cents / len(people) for name in people}
    cents = _largest_remainder(raw, bill_cents)
    notes = {note.person.casefold(): note.note for note in plan.notes}
    return [{
        "person": name,
        "items": lines[name],
        "items_total": round(item_totals[name], 2),
        "extras": round(cents[name] / 100 - item_totals[name], 2),
        "amount": cents[name] / 100,
        "note": notes.get(name.casefold(), ""),
    } for name in people]


def _spread(item, portions, lines, item_totals, reason):
    weight_sum = sum(weight for _, weight in portions)
    sharers = [name for name, _ in portions]
    for name, weight in portions:
        amount = item.line_total * weight / weight_sum
        item_totals[name] += amount
        lines[name].append({"name": item.name, "amount": round(amount, 2), "shared_with": [s for s in sharers if s != name], "reason": reason})


def _largest_remainder(raw: dict[str, float], total: int) -> dict[str, int]:
    """Round to whole cents while keeping the exact total."""
    floors = {name: int(value) for name, value in raw.items()}
    left = total - sum(floors.values())
    for name in sorted(raw, key=lambda n: raw[n] - floors[n], reverse=True)[:left]:
        floors[name] += 1
    return floors
