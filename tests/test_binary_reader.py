"""Unit tests for ChunkedBinaryReaderAdapter."""

from pathlib import Path
import pytest

from AMS_Parser.adapters.file_reader import ChunkedBinaryReaderAdapter
from AMS_Parser.domain.enums import LOG_BLOCK_SIZE_B


def test_reader_empty_file(tmp_path: Path):
    empty_file = tmp_path / "empty.bin"
    empty_file.write_bytes(b"")

    reader = ChunkedBinaryReaderAdapter(block_size_bytes=LOG_BLOCK_SIZE_B)
    assert reader.get_file_size(empty_file) == 0

    blocks = list(reader.stream_blocks(empty_file))
    assert len(blocks) == 0


def test_reader_chunk_size_alignment(tmp_path: Path):
    test_file = tmp_path / "test.bin"
    block_a = b"A" * LOG_BLOCK_SIZE_B
    block_b = b"B" * LOG_BLOCK_SIZE_B
    block_c = b"C" * 100  # Partial trailing block
    test_file.write_bytes(block_a + block_b + block_c)

    reader = ChunkedBinaryReaderAdapter(block_size_bytes=LOG_BLOCK_SIZE_B)
    assert reader.get_file_size(test_file) == (2 * LOG_BLOCK_SIZE_B) + 100

    blocks = list(reader.stream_blocks(test_file))
    assert len(blocks) == 3
    assert blocks[0] == block_a
    assert blocks[1] == block_b
    assert blocks[2] == block_c
