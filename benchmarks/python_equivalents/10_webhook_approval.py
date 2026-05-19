import logging
import time
from decimal import Decimal
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

APPROVAL_WEBHOOK_URL = "https://approvals.company.com/lumen"
APPROVAL_TIMEOUT_SECONDS = 300

class ApprovalTimeoutError(Exception):
    pass

class ApprovalDeniedError(Exception):
    pass

def request_approval(amount: Decimal, timeout: int = APPROVAL_TIMEOUT_SECONDS) -> bool:
    payload = {"action": "critical_transfer", "amount": str(amount)}
    try:
        response = httpx.post(APPROVAL_WEBHOOK_URL, json=payload, timeout=timeout)
        response.raise_for_status()
        data = response.json()
        return data.get("approved", False)
    except httpx.TimeoutException:
        raise ApprovalTimeoutError(f"Approval request timed out after {timeout}s")

def transfer_money(from_account: str, to_account: str, amount: Decimal) -> str:
    logger.info(f"Transferring {amount} from {from_account} to {to_account}")
    txn_id = "txn_placeholder"
    _schedule_reversal(txn_id, hours=1)
    return txn_id

def _schedule_reversal(txn_id: str, hours: int) -> None:
    pass

def critical_transfer(amount: Decimal) -> None:
    if amount <= Decimal("10000"):
        raise ValueError("requires: amount > 10000")
    approved = request_approval(amount)
    if not approved:
        raise ApprovalDeniedError("Transfer not approved via webhook")
    txn = transfer_money(
        from_account="treasury",
        to_account="operations",
        amount=amount,
    )
    logger.info(f"Critical transfer complete: {txn}")

if __name__ == "__main__":
    critical_transfer(Decimal("50000"))
