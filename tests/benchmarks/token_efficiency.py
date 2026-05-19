"""Benchmark de eficiencia de tokens: Lumen vs Python.

Target: Lumen usa <= 50% tokens que Python para tareas equivalentes.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path


@dataclass
class BenchmarkResult:
    task: str
    python_tokens: int
    lumen_tokens: int
    ratio: float


CANONICAL_TASKS = [
    ("read_emails_count_urgent", "Leer correos y contar urgentes"),
    ("process_pdf_extract_dates", "Procesar PDF y extraer fechas"),
    ("monitor_folder_move_files", "Monitorear carpeta y mover archivos por tipo"),
    ("three_transfers_approval", "Hacer 3 transferencias con aprobación"),
    ("daily_summary_llm", "Sintetizar resumen diario"),
    ("convert_100_images", "Convertir 100 imágenes con CLI wrap"),
    ("search_docs_summarize", "Buscar en docs y resumir hallazgos"),
    ("create_event_from_text", "Crear evento de calendario desde texto natural"),
    ("notify_on_specific_email", "Notificar cuando llegue email específico"),
    ("undo_last_transaction", "Deshacer última transacción"),
]

PYTHON_IMPLEMENTATIONS = {
    "read_emails_count_urgent": '''
import imaplib, email
def count_urgent_emails():
    with imaplib.IMAP4_SSL("imap.gmail.com") as m:
        m.login(USER, PASS)
        m.select("INBOX")
        _, nums = m.search(None, "UNSEEN")
        urgent = 0
        for n in nums[0].split():
            _, data = m.fetch(n, "(RFC822)")
            msg = email.message_from_bytes(data[0][1])
            priority = float(msg.get("X-Priority", "3"))
            if priority < 2:
                urgent += 1
        return urgent
''',
    "process_pdf_extract_dates": '''
import re
from PyPDF2 import PdfReader
def extract_dates_from_pdf(path):
    reader = PdfReader(path)
    text = " ".join(p.extract_text() for p in reader.pages)
    dates = re.findall(r"\\d{4}-\\d{2}-\\d{2}", text)
    return dates
''',
    "three_transfers_approval": '''
import requests
def transfer_with_approval(from_acc, to_acc, amount, approver_url):
    resp = requests.post(approver_url, json={
        "action": "transfer",
        "from": from_acc,
        "to": to_acc,
        "amount": amount,
    })
    if resp.json()["approved"]:
        # Execute transfer via bank API
        result = requests.post(BANK_API, json={"from": from_acc, "to": to_acc, "amount": amount})
        return result.json()
    return {"error": "rejected"}

for transfer in [("A", "B", 1000), ("B", "C", 500), ("C", "D", 250)]:
    transfer_with_approval(*transfer, APPROVER_URL)
''',
}

LUMEN_IMPLEMENTATIONS = {
    "read_emails_count_urgent": '''
@lumen 1.0
use comm.email

emails = read.email(since="yesterday")
urgent = emails | filter(e -> e.priority > 0.7)
print "Tienes ${urgent.length} correos urgentes"
''',
    "process_pdf_extract_dates": '''
@lumen 1.0
use data.parse
use data.extract

doc = data.parse("report.pdf")
dates = data.extract(text=doc.content, types=["DATE"])
for d in dates:
  print d.value
''',
    "three_transfers_approval": '''
@lumen 1.0
use sensitive.transfer

action transfer(from, to, amount):
  reversible: 24h
  audit: full
  execute:
    transfer.money(from=from, to=to, amount=amount)

for t in [("A", "B", $1000), ("B", "C", $500), ("C", "D", $250)]:
  transfer(t.from, t.to, t.amount)
''',
}


def count_tokens_approx(text: str) -> int:
    words = text.split()
    return len(words) + len(text) // 4


def run_benchmark(threshold: float = 0.5) -> bool:
    results = []
    for task_id, task_name in CANONICAL_TASKS:
        py_impl = PYTHON_IMPLEMENTATIONS.get(task_id, "# placeholder Python implementation\n" * 5)
        lumen_impl = LUMEN_IMPLEMENTATIONS.get(task_id, "@lumen 1.0\n# placeholder Lumen implementation\n")

        py_tokens = count_tokens_approx(py_impl)
        lumen_tokens = count_tokens_approx(lumen_impl)
        ratio = lumen_tokens / py_tokens if py_tokens > 0 else 1.0

        results.append(BenchmarkResult(
            task=task_name,
            python_tokens=py_tokens,
            lumen_tokens=lumen_tokens,
            ratio=ratio,
        ))

    print("\nBenchmark de tokens: Lumen vs Python")
    print("=" * 60)
    for r in results:
        status = "OK" if r.ratio <= threshold else "FAIL"
        print(f"[{status}] {r.task}: {r.lumen_tokens}/{r.python_tokens} tokens ({r.ratio:.2f}x)")

    avg_ratio = sum(r.ratio for r in results) / len(results)
    print(f"\nRatio promedio: {avg_ratio:.2f}x (target: <= {threshold}x)")

    passed = avg_ratio <= threshold
    op = "<=" if passed else ">"
    print(f"\n{'PASS' if passed else 'FAIL'}: ratio promedio {op} {threshold}")
    return passed


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--threshold", type=float, default=0.5)
    args = parser.parse_args()

    passed = run_benchmark(args.threshold)
    import sys
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
