from datetime import date

import pytest

from edit_dialogs import parse_date_text


def test_parse_date_text_accepts_common_formats():
    assert parse_date_text("2026-07-15") == date(2026, 7, 15)
    assert parse_date_text("07/15/2026") == date(2026, 7, 15)
    assert parse_date_text("July 15, 2026") == date(2026, 7, 15)


def test_parse_date_text_rejects_invalid_input():
    with pytest.raises(ValueError):
        parse_date_text("not-a-date")
