"""Persistent runtime state for dashboard automation."""

from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class RuntimeStore:
    def __init__(self, root_dir: str | Path) -> None:
        self.root_dir = Path(root_dir)
        self.runtime_dir = self.root_dir / "runtime"
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        self.history_path = self.runtime_dir / "trade_history.csv"
        self.kill_switch_path = self.runtime_dir / "KILL_SWITCH"

    def append_event(self, event: dict[str, Any]) -> None:
        row = {
            "timestamp": event.get("timestamp") or datetime.now(timezone.utc).isoformat(),
            "broker": event.get("broker", ""),
            "symbol": event.get("symbol", ""),
            "strategy": event.get("strategy", ""),
            "signal": event.get("signal", ""),
            "status": event.get("status", ""),
            "price": event.get("price", ""),
            "quantity": event.get("quantity", ""),
            "order_id": event.get("order_id", ""),
            "message": event.get("message", ""),
        }
        write_header = not self.history_path.exists()
        with self.history_path.open("a", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(row))
            if write_header:
                writer.writeheader()
            writer.writerow(row)

    def read_events(self, limit: int = 200) -> list[dict[str, str]]:
        if not self.history_path.exists():
            return []
        with self.history_path.open("r", newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        return rows[-limit:]

    def activate_kill_switch(self, reason: str = "manual") -> None:
        self.kill_switch_path.write_text(
            f"{datetime.now(timezone.utc).isoformat()} | {reason}",
            encoding="utf-8",
        )

    def clear_kill_switch(self) -> None:
        if self.kill_switch_path.exists():
            self.kill_switch_path.unlink()

    def kill_switch_active(self) -> bool:
        return self.kill_switch_path.exists()

    def kill_switch_reason(self) -> str:
        if not self.kill_switch_path.exists():
            return ""
        return self.kill_switch_path.read_text(encoding="utf-8", errors="ignore")

