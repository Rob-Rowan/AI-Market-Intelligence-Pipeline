"""Throwaway behavioral smoke test for the refactored data_extract.py."""

from __future__ import annotations
import gspread
from modules.data_extract import DataExtractor
import hashlib
import logging
from types import SimpleNamespace

logging.disable(logging.CRITICAL)



KNOWN_HASH = hashlib.md5(b"known.pdffile1").hexdigest()


class FakeSheet:
    def __init__(self, values: list[str] | None = None) -> None:
        self.values = values if values is not None else ["Hash", KNOWN_HASH]
        self.col_values_calls = 0

    def col_values(self, col: int) -> list[str]:
        self.col_values_calls += 1
        if isinstance(self.values, Exception):
            raise self.values
        return self.values


class FakeDrive:
    def __init__(self, files: list[dict]) -> None:
        self._files = files

    def files(self) -> "FakeDriveFiles":
        return FakeDriveFiles(self._files)


class FakeDriveFiles:
    def __init__(self, files: list[dict]) -> None:
        self._files = files

    def list(self, q: str = "", fields: str = "") -> "FakeListRequest":
        return FakeListRequest(self._files)


class FakeListRequest:
    def __init__(self, files: list[dict]) -> None:
        self._files = files

    def execute(self) -> dict:
        return {"files": self._files}


class FakeGspread:
    def __init__(self, sheet: FakeSheet) -> None:
        self._sheet = sheet

    def open_by_key(self, sheet_id: str) -> "FakeSpreadsheet":
        return FakeSpreadsheet(self._sheet)


class FakeSpreadsheet:
    def __init__(self, sheet: FakeSheet) -> None:
        self._sheet = sheet

    def worksheet(self, name: str) -> FakeSheet:
        return self._sheet


def build_extractor(sheet: FakeSheet, drive: FakeDrive) -> DataExtractor:
    services = SimpleNamespace(gspread_client=FakeGspread(sheet), drive_service=drive)
    extractor = DataExtractor.__new__(DataExtractor)
    extractor.services = services
    extractor.sheet = sheet
    extractor._extract_file_text = lambda file_id, mime: f"content of {file_id}"
    return extractor


def test_n_plus_one_fix() -> None:
    sheet = FakeSheet()
    drive = FakeDrive(
        [
            {"id": "file1", "name": "known.pdf", "mimeType": "application/pdf"},
            {"id": "file2", "name": "new.txt", "mimeType": "text/plain"},
            {"id": "file3", "name": "also_new.pdf", "mimeType": "application/pdf"},
        ]
    )
    extractor = build_extractor(sheet, drive)
    items = extractor.fetch_drive_transcripts("folder123")

    assert sheet.col_values_calls == 1, (
        f"dedup sheet read {sheet.col_values_calls} times; expected exactly 1"
    )
    titles = [i["title"] for i in items]
    assert titles == [
        "TRANSCRIPT: new.txt",
        "TRANSCRIPT: also_new.pdf",
    ], f"unexpected results: {titles}"
    assert items[0]["hash"] == hashlib.md5(b"new.txtfile2").hexdigest()
    assert sheet.col_values_calls == 1, "in-memory set must prevent re-reading the sheet"
    print("PASS test_n_plus_one_fix")


def test_dedup_set_loaded_before_loop() -> None:
    second = hashlib.md5(b"known_too.txtfile2").hexdigest()
    sheet = FakeSheet(["Hash", KNOWN_HASH, second])
    drive = FakeDrive(
        [
            {"id": "file1", "name": "known.pdf", "mimeType": "application/pdf"},
            {"id": "file2", "name": "known_too.txt", "mimeType": "text/plain"},
        ]
    )
    extractor = build_extractor(sheet, drive)
    items = extractor.fetch_drive_transcripts("bucket")
    assert items == [], f"both files should be deduplicated, got: {items}"
    print("PASS test_dedup_set_loaded_before_loop")


def test_fail_safe_abort_on_sheet_error() -> None:
    sheet = FakeSheet(RuntimeError("sheets unavailable"))
    drive = FakeDrive([{"id": "x", "name": "y.txt", "mimeType": "text/plain"}])
    extractor = build_extractor(sheet, drive)
    items = extractor.fetch_drive_transcripts("bucket")
    assert items == [], f"run must abort when dedup state is unavailable, got: {items}"
    print("PASS test_fail_safe_abort_on_sheet_error")


def test_hash_stability() -> None:
    a = DataExtractor._generate_hash(None, "title", "id1")
    b = DataExtractor._generate_hash(None, "title", "id1")
    assert a == b
    assert a != DataExtractor._generate_hash(None, "title", "id2")
    assert a == hashlib.md5(b"titleid1").hexdigest()
    print("PASS test_hash_stability")


if __name__ == "__main__":
    test_n_plus_one_fix()
    test_dedup_set_loaded_before_loop()
    test_fail_safe_abort_on_sheet_error()
    test_hash_stability()
    print("ALL SMOKE TESTS PASSED")