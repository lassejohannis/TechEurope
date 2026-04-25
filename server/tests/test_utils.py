"""Tests for utility helpers."""

from __future__ import annotations

import pytest

from server.utils.normalize import parse_currency, parse_date_iso, parse_percent


class TestParseCurrency:
    def test_plain_float(self):
        assert parse_currency(12.5) == 12.5

    def test_integer(self):
        assert parse_currency(100) == 100.0

    def test_string_with_symbol(self):
        assert parse_currency("$1,234.56") == pytest.approx(1234.56)

    def test_string_euro(self):
        assert parse_currency("€99.99") == pytest.approx(99.99)

    def test_none_returns_none(self):
        assert parse_currency(None) is None

    def test_empty_string_returns_none(self):
        assert parse_currency("") is None

    def test_just_letters_returns_none(self):
        assert parse_currency("N/A") is None


class TestParseDateIso:
    def test_iso_passthrough(self):
        assert parse_date_iso("2024-03-15") == "2024-03-15"

    def test_slash_format(self):
        assert parse_date_iso("15/03/2024") == "2024-03-15"

    def test_dot_format(self):
        assert parse_date_iso("15.03.2024") == "2024-03-15"

    def test_datetime_string(self):
        assert parse_date_iso("2024-03-15T10:30:00") == "2024-03-15"

    def test_none_returns_none(self):
        assert parse_date_iso(None) is None

    def test_empty_returns_none(self):
        assert parse_date_iso("") is None

    def test_unknown_format_passthrough(self):
        # Unknown formats are passed through as-is
        result = parse_date_iso("March 2024")
        assert result == "March 2024"


class TestParsePercent:
    def test_float(self):
        assert parse_percent(0.5) == 0.5

    def test_string_percent(self):
        assert parse_percent("85.5%") == pytest.approx(85.5)

    def test_none_returns_none(self):
        assert parse_percent(None) is None
