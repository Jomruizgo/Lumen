import logging
from decimal import Decimal
from typing import Optional

logger = logging.getLogger(__name__)

class SupplierNotFoundError(Exception):
    pass

def resolve_supplier(name: str) -> dict:
    suppliers = _query_crm(name)
    if len(suppliers) == 1:
        return suppliers[0]
    elif len(suppliers) > 1:
        answer = input(f"¿Cuál proveedor? {suppliers}: ")
        return next(s for s in suppliers if answer in s["name"])
    else:
        raise SupplierNotFoundError(f"Proveedor no encontrado: {name}")

def _query_crm(name: str) -> list:
    return []  # placeholder

def transfer_money(from_account: str, to_account: str, amount: Decimal) -> str:
    logger.info(f"Transferring {amount} from {from_account} to {to_account}")
    transaction_id = "txn_placeholder"
    return transaction_id

def pay_supplier(supplier_name: str, amount: Decimal) -> None:
    if amount <= 0:
        raise ValueError("amount must be positive")
    supplier = resolve_supplier(supplier_name)
    txn = transfer_money(
        from_account="company_account",
        to_account=supplier["account"],
        amount=amount,
    )
    logger.info(f"Payment complete: {txn}")
    _schedule_reversal(txn, hours=24)

def _schedule_reversal(txn_id: str, hours: int) -> None:
    pass

if __name__ == "__main__":
    pay_supplier("Pedro García", Decimal("1000"))
