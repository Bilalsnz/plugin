"""Seed a local PatchReview queue for the offline UI and print pending ids."""
import difflib, hashlib, json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
QUEUE = ROOT / "data" / "pending.json"

def proposal(pid, path, tool, old, new):
    diff = "".join(difflib.unified_diff(old.splitlines(keepends=True), new.splitlines(keepends=True), fromfile="a/" + path, tofile="b/" + path, lineterm="\n"))
    now = datetime.now(timezone.utc).isoformat()
    return {"id": pid, "path": path, "tool": tool, "old_content": old, "new_content": new, "diff": diff,
            "old_hash": hashlib.sha256(old.encode()).hexdigest(), "new_hash": hashlib.sha256(new.encode()).hexdigest(),
            "status": "pending", "created_at": now, "updated_at": now, "reason": None}

def main():
    QUEUE.parent.mkdir(parents=True, exist_ok=True)
    items = [
        proposal("a17c92e1", "src/wallet.ts", "write_file",
                 "export function approve(tx: Transaction) {\n  return wallet.send(tx);\n}\n",
                 "export function approve(tx: Transaction) {\n  if (!tx || tx.amount <= 0) throw new Error('Invalid transaction');\n  if (!wallet.isConnected()) throw new Error('Wallet not connected');\n  return wallet.send(tx);\n}\n"),
        proposal("b42d8f06", "README.md", "str_replace",
                 "# Starter App\n\nA demo project.\n",
                 "# PatchReview\n\nNothing writes to disk until the human accepts the diff.\n")
    ]
    QUEUE.write_text(json.dumps(items, indent=2), encoding="utf-8")
    print("Pending proposal ids:")
    for item in items: print("- " + item["id"] + "  " + item["path"])

if __name__ == "__main__": main()
