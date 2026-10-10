"""Binary reader port definition."""

from pathlib import Path
from typing import Iterator, Protocol


class BinaryReaderPort(Protocol):
    """Port for streaming block-aligned chunks from physical storage."""

    def stream_blocks(self, file_path: Path) -> Iterator[bytes]:
        """Yields sequential fixed-size blocks (e.g. 4096 B) from the target file."""
        ...

    def get_file_size(self, file_path: Path) -> int:
        """Returns the total file size in bytes."""
        ...
