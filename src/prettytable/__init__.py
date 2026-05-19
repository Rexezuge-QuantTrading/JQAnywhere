"""Small PrettyTable compatibility subset for strategy log output."""

from __future__ import annotations


class PrettyTable:
    def __init__(self):
        self.field_names = []
        self.align = {}
        self._rows = []

    def add_row(self, row) -> None:
        self._rows.append(["" if value is None else str(value) for value in row])

    def __str__(self) -> str:
        rows = [[str(value) for value in self.field_names], *self._rows]
        if not rows:
            return ""
        widths = [max(len(row[index]) if index < len(row) else 0 for row in rows) for index in range(len(rows[0]))]
        separator = "+" + "+".join("-" * (width + 2) for width in widths) + "+"
        lines = [separator, _format_row(rows[0], widths), separator]
        lines.extend(_format_row(row, widths) for row in self._rows)
        lines.append(separator)
        return "\n".join(lines)


def _format_row(row, widths) -> str:
    cells = []
    for index, width in enumerate(widths):
        value = row[index] if index < len(row) else ""
        cells.append(f" {value:<{width}} ")
    return "|" + "|".join(cells) + "|"


__all__ = ["PrettyTable"]
