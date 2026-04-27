"""Persistent runtime state for dashboard automation."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class RuntimeStore:
    def __init__(self, root_dir: str | Path) -> None:
        self.root_dir = Path(root_dir)
        self.runtime_dir = self.root_dir / "runtime"
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.runtime_dir / "trading_bot.db"
        self.kill_switch_path = self.runtime_dir / "KILL_SWITCH"
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path, timeout=30)
        connection.row_factory = sqlite3.Row
        return connection

    def _init_db(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS trade_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    broker TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    strategy TEXT NOT NULL,
                    signal TEXT NOT NULL,
                    status TEXT NOT NULL,
                    price REAL,
                    quantity REAL,
                    order_id TEXT,
                    message TEXT NOT NULL
                )
                """
            )
            connection.execute("CREATE INDEX IF NOT EXISTS idx_trade_events_timestamp ON trade_events(timestamp)")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_trade_events_symbol ON trade_events(symbol)")
            connection.commit()

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
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO trade_events (
                    timestamp, broker, symbol, strategy, signal, status,
                    price, quantity, order_id, message
                ) VALUES (
                    :timestamp, :broker, :symbol, :strategy, :signal, :status,
                    :price, :quantity, :order_id, :message
                )
                """,
                row,
            )
            connection.commit()

    def read_events(self, limit: int = 200) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT timestamp, broker, symbol, strategy, signal, status,
                       price, quantity, order_id, message
                FROM trade_events
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

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
