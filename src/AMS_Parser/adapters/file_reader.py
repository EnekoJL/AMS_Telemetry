"""Adapter for streaming binary files in fixed-size blocks."""

import os
from pathlib import Path
from typing import Iterator

from AMS_Parser.domain.enums import LOG_BLOCK_SIZE_B


class ChunkedBinaryReaderAdapter:
    """Streams block-aligned chunks from local disk without loading entire files into memory."""

    def __init__(self, block_size_bytes: int = LOG_BLOCK_SIZE_B) -> None:
        self._block_size = block_size_bytes

    def stream_blocks(self, file_path: Path) -> Iterator[bytes]:
        """Yields sequential fixed-size blocks (e.g. 4096 B) from the target file."""
        with open(file_path, "rb") as f:
            while True:
                chunk = f.read(self._block_size)
                if not chunk:
                    break
                yield chunk

    def get_file_size(self, file_path: Path) -> int:
        """Returns the total file size in bytes."""
        return os.path.getsize(file_path)
