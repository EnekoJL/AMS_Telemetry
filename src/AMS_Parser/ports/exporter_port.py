"""Telemetry exporter port definition."""

from pathlib import Path
from typing import Generic, Iterable, Protocol, TypeVar

T = TypeVar("T")


class TelemetryExporterPort(Protocol, Generic[T]):
    """Port interface for persisting domain records to external formats (CSV, SQLite, etc.)."""

    def export(self, records: Iterable[T], destination_file: Path) -> Path:
        """Exports a stream of domain records to the specified destination path."""
        ...
