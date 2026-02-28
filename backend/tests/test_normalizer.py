"""
Unit tests for scraper/normalizer.py

Run:
    cd backend
    .venv/bin/python -m pytest tests/ -v
"""

import sys
sys.path.insert(0, ".")

import pytest
from scraper.normalizer import (
    normalize,
    _parse_abv,
    _parse_age,
    _parse_price,
    _parse_rating,
    _normalize_category,
    _normalize_region,
)


# ── _parse_abv ─────────────────────────────────────────────────────────────

class TestParseAbv:
    def test_plain_number(self):
        assert _parse_abv("46.0") == 46.0

    def test_with_percent(self):
        assert _parse_abv("46.0%") == 46.0

    def test_with_abv_label(self):
        assert _parse_abv("40% ABV") == 40.0

    def test_comma_decimal(self):
        assert _parse_abv("46,0") == 46.0

    def test_integer(self):
        assert _parse_abv("40") == 40.0

    def test_too_low(self):
        assert _parse_abv("9.5") is None

    def test_too_high(self):
        assert _parse_abv("96.0") is None

    def test_none_input(self):
        assert _parse_abv(None) is None

    def test_garbage(self):
        assert _parse_abv("no abv here") is None

    def test_cask_strength(self):
        assert _parse_abv("64.8%") == 64.8

    def test_rounding(self):
        assert _parse_abv("46.123") == 46.1


# ── _parse_age ─────────────────────────────────────────────────────────────

class TestParseAge:
    def test_plain_number(self):
        assert _parse_age("12") == 12

    def test_year_old(self):
        assert _parse_age("18 Year Old") == 18

    def test_yr(self):
        assert _parse_age("10yr") == 10

    def test_yo(self):
        assert _parse_age("21YO") == 21

    def test_nas(self):
        assert _parse_age("NAS") is None

    def test_no_age_statement(self):
        assert _parse_age("No Age Statement") is None

    def test_too_old(self):
        assert _parse_age("81") is None

    def test_zero(self):
        assert _parse_age("0") is None

    def test_none_input(self):
        assert _parse_age(None) is None

    def test_garbage(self):
        assert _parse_age("not an age") is None


# ── _parse_price ───────────────────────────────────────────────────────────

class TestParsePrice:
    def test_plain_number(self):
        assert _parse_price("49.99") == 49.99

    def test_dollar_sign(self):
        assert _parse_price("$49.99") == 49.99

    def test_with_commas(self):
        assert _parse_price("1,299.00") == 1299.0

    def test_gbp_conversion(self):
        # £35 from masterofmalt → ~$44.45
        result = _parse_price("£35.00", source="masterofmalt")
        assert result == pytest.approx(44.45, abs=0.1)

    def test_nok_conversion(self):
        # 799 NOK from vinmonopolet → ~$72.71
        result = _parse_price("799", source="vinmonopolet")
        assert result == pytest.approx(72.71, abs=0.5)

    def test_usd_no_conversion(self):
        assert _parse_price("50.00", source="distiller") == 50.0

    def test_too_low(self):
        assert _parse_price("0.50") is None

    def test_too_high(self):
        assert _parse_price("60000") is None

    def test_none_input(self):
        assert _parse_price(None) is None


# ── _parse_rating ──────────────────────────────────────────────────────────

class TestParseRating:
    def test_zero_to_five(self):
        avg, count = _parse_rating("4.5")
        assert avg == 4.5
        assert count == 0

    def test_whiskybase_scale(self):
        # 84.5 / 100 * 5 = 4.225 → rounds to 4.22
        avg, count = _parse_rating("84.5")
        assert avg == pytest.approx(4.22, abs=0.01)

    def test_with_vote_count(self):
        avg, count = _parse_rating("84.5 (1,234 votes)")
        assert avg == pytest.approx(4.22, abs=0.01)
        assert count == 1234

    def test_none_input(self):
        avg, count = _parse_rating(None)
        assert avg == 0.0
        assert count == 0

    def test_max_clamp(self):
        # 101 on 0-100 scale → 5.05 → clamped to 5.0
        avg, _ = _parse_rating("101")
        assert avg == 5.0


# ── _normalize_category ───────────────────────────────────────────────────

class TestNormalizeCategory:
    def test_single_malt(self):
        assert _normalize_category("Single Malt Scotch Whisky", "scotland") == "single malt"

    def test_bourbon(self):
        assert _normalize_category("Kentucky Straight Bourbon", "usa") == "bourbon"

    def test_tennessee(self):
        assert _normalize_category("Tennessee Whiskey", "usa") == "bourbon"

    def test_rye(self):
        assert _normalize_category("Straight Rye Whiskey", "usa") == "rye"

    def test_irish(self):
        assert _normalize_category("Irish Whiskey", "ireland") == "irish"

    def test_japanese(self):
        assert _normalize_category("Japanese Whisky", "japan") == "japanese"

    def test_canadian(self):
        assert _normalize_category("Canadian Whisky", "canada") == "canadian"

    def test_country_fallback_scotland(self):
        assert _normalize_category("", "scotland") == "scotch"

    def test_country_fallback_usa(self):
        assert _normalize_category("", "usa") == "bourbon"

    def test_wheat_maps_to_bourbon(self):
        assert _normalize_category("Wheat Whiskey", "usa") == "bourbon"

    def test_blended_scotch(self):
        assert _normalize_category("Blended Scotch Whisky", "scotland") == "scotch"


# ── _normalize_region ─────────────────────────────────────────────────────

class TestNormalizeRegion:
    def test_islay(self):
        assert _normalize_region("islay") == "Islay"

    def test_speyside(self):
        assert _normalize_region("Speyside") == "Speyside"

    def test_highlands_variant(self):
        assert _normalize_region("highland") == "Highlands"

    def test_kentucky(self):
        assert _normalize_region("kentucky") == "Kentucky"

    def test_empty(self):
        assert _normalize_region("") is None

    def test_none_input(self):
        assert _normalize_region(None) is None


# ── normalize() end-to-end ─────────────────────────────────────────────────

class TestNormalize:
    def _raw(self, **kwargs):
        base = {
            "name": "Test Whiskey 12 Year Old",
            "distillery": "Test Distillery",
            "category": "Single Malt Scotch Whisky",
            "country": "scotland",
            "abv_str": "46.0%",
            "age_str": "12",
            "source": "distiller",
        }
        base.update(kwargs)
        return base

    def test_basic_normalize(self):
        result = normalize(self._raw())
        assert result is not None
        assert result["name"] == "Test Whiskey 12 Year Old"
        assert result["abv"] == 46.0
        assert result["age"] == 12
        assert result["category"] == "single malt"

    def test_missing_name_returns_none(self):
        assert normalize(self._raw(name="")) is None
        assert normalize(self._raw(name=None)) is None

    def test_missing_abv_returns_none(self):
        assert normalize(self._raw(abv_str=None)) is None

    def test_invalid_abv_returns_none(self):
        assert normalize(self._raw(abv_str="999%")) is None

    def test_na_distillery_becomes_unknown(self):
        result = normalize(self._raw(distillery="N/A"))
        assert result["distillery"] == "Unknown"

    def test_description_truncated_to_1000(self):
        result = normalize(self._raw(description="x" * 2000))
        assert len(result["description"]) == 1000

    def test_nas_age_is_none(self):
        result = normalize(self._raw(age_str="NAS"))
        assert result["age"] is None

    def test_gbp_price_converted(self):
        result = normalize(self._raw(price_str="£50.00", source="masterofmalt"))
        assert result["price_usd"] == pytest.approx(63.5, abs=0.5)

    def test_nok_price_converted(self):
        result = normalize(self._raw(price_str="799", source="vinmonopolet"))
        assert result["price_usd"] == pytest.approx(72.71, abs=0.5)
