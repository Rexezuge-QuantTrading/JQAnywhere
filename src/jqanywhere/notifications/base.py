"""Notification interfaces."""

from __future__ import annotations

from abc import ABC, abstractmethod


class Notifier(ABC):
    @abstractmethod
    def send(self, subject: str, message: str) -> None:
        raise NotImplementedError
