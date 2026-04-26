"""Configuration loading with environment expansion and validation."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv


ENV_PATTERN = re.compile(r"\$\{([^}^{]+)\}")


@dataclass(frozen=True)
class AppConfig:
    settings: dict[str, Any]
    symbols: dict[str, Any]
    strategies: dict[str, Any]
    root_dir: Path

    @property
    def mode(self) -> str:
        return str(self.settings.get("mode", "paper")).lower()

    @property
    def live_requested(self) -> bool:
        return bool(self.settings.get("live_trading", False))


def _expand_env(value: Any) -> Any:
    if isinstance(value, str):
        return ENV_PATTERN.sub(lambda m: os.getenv(m.group(1), ""), value)
    if isinstance(value, list):
        return [_expand_env(item) for item in value]
    if isinstance(value, dict):
        return {key: _expand_env(item) for key, item in value.items()}
    return value


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Missing config file: {path}")
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Config file must contain a mapping: {path}")
    return _expand_env(data)


class ConfigLoader:
    """Loads YAML config files and .env values from the project root."""

    def __init__(self, root_dir: str | Path | None = None) -> None:
        self.root_dir = Path(root_dir or Path(__file__).resolve().parents[1])
        load_dotenv(self.root_dir / ".env")

    def load(self) -> AppConfig:
        config_dir = self.root_dir / "config"
        app_config = AppConfig(
            settings=_load_yaml(config_dir / "settings.yaml"),
            symbols=_load_yaml(config_dir / "symbols.yaml"),
            strategies=_load_yaml(config_dir / "strategies.yaml"),
            root_dir=self.root_dir,
        )
        self.validate_safety(app_config)
        return app_config

    @staticmethod
    def validate_safety(config: AppConfig) -> None:
        mode = str(config.settings.get("mode", "paper")).lower()
        if mode not in {"backtest", "paper", "quote", "account", "live"}:
            raise ValueError("mode must be one of: backtest, paper, quote, account, live")

        env_live = os.getenv("LIVE_TRADING", "false").lower() == "true"
        cfg_live = bool(config.settings.get("live_trading", False))
        user_confirmed = bool(config.settings.get("user_confirm_live", False))
        broker_allows_live = bool(config.settings.get("broker", {}).get("allow_live", False))

        if mode == "live" or cfg_live:
            if not (env_live and cfg_live and user_confirmed and broker_allows_live):
                raise PermissionError(
                    "Live trading refused. Require mode=live, LIVE_TRADING=true, "
                    "live_trading=true, user_confirm_live=true, and broker.allow_live=true."
                )
