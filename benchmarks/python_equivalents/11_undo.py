import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional, Union

logger = logging.getLogger(__name__)

def query_reversible_transfers(since_hours: int = 2) -> list[dict]:
    cutoff = datetime.utcnow() - timedelta(hours=since_hours)
    # Placeholder: query audit log for reversible transfer.money actions
    return []

def undo_action(action_id: str) -> Union[dict, Exception]:
    logger.info(f"Undoing action {action_id}")
    # Placeholder: call reversal API
    try:
        result = _call_reversal_api(action_id)
        return result
    except Exception as exc:
        return exc

def _call_reversal_api(action_id: str) -> dict:
    return {"status": "ok"}

def main() -> None:
    recent = query_reversible_transfers(since_hours=2)
    print("Transferencias deshacibles:")
    for t in recent:
        print(f"{t['action_id']}: {t.get('amount')} a {t.get('to')}")

    target_id = input("¿Cuál ID deshacer? ")
    result = undo_action(target_id)
    if isinstance(result, Exception):
        print(f"No se pudo: {result}")
    else:
        print("Deshecho")

if __name__ == "__main__":
    main()
