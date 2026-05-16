"""Small JoinQuant-style logger."""

from __future__ import annotations

from dataclasses import dataclass, field


LEVELS = {"debug": 10, "info": 20, "warn": 30, "warning": 30, "error": 40}


@dataclass
class BufferedLogger:
    level: int = 20
    records: list[str] = field(default_factory=list)

    def set_level(self, _name: str, level: str) -> None:
        self.level = LEVELS.get(level.lower(), self.level)

    def debug(self, message: object) -> None:
        self._write("debug", message)

    def info(self, message: object) -> None:
        self._write("info", message)

    def warn(self, message: object) -> None:
        self._write("warn", message)

    def warning(self, message: object) -> None:
        self.warn(message)

    def error(self, message: object) -> None:
        self._write("error", message)

    def _write(self, level: str, message: object) -> None:
        if LEVELS[level] >= self.level:
            self.records.append(f"[{level.upper()}] {message}")

    def flush_text(self) -> str:
        return "\n".join(self.records)
