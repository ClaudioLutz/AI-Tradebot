"""tests.test_market_data

Story 003-006: Unit Tests with Mocked Saxo Market Data Responses

These tests are deterministic and do not make external network calls.
We mock SaxoClient.get_with_headers to simulate Saxo endpoint responses.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch, Mock

import pytest

from data.market_data import (
    SUPPORTED_HORIZON_MINUTES,
    derive_data_quality_from_quote,
    evaluate_bar_freshness,
    evaluate_quote_freshness,
    get_latest_quotes,
    get_ohlc_bars,
    normalize_bar_from_chart_sample,
    normalize_quote_from_infoprice,
)
from data.saxo_client import parse_rate_limit_headers


def test_parse_iso8601_naive_timestamp_assumes_utc():
    # Saxo normally returns 'Z', but if it ever returns naive timestamps
    # we should treat them as UTC instead of raising.
    quote = {
        "bid": 1.0,
        "ask": 1.1,
        "mid": 1.05,
        "last_updated": "2025-12-13T08:00:00",  # naive
        "delayed_by_minutes": 0,
        "market_state": "Open",
    }
    now = datetime(2025, 12, 13, 8, 10, 0, tzinfo=timezone.utc)

    fresh = evaluate_quote_freshness(quote, now=now, stale_quote_seconds=300)
    assert fresh["age_seconds"] == pytest.approx(600.0)
    assert fresh["is_stale"] is True


@pytest.fixture
def instruments():
    return [
        {"asset_type": "Stock", "uic": 211, "symbol": "AAPL"},
        {"asset_type": "Stock", "uic": 999999, "symbol": "INVALID"},
    ]


def test_infoprices_list_success_and_missing_mid_derivation():
    item = {
        "Uic": 211,
        "LastUpdated": "2025-12-13T08:30:00Z",
        "Quote": {
            "Bid": 150.25,
            "Ask": 150.35,
            "Mid": None,
            "DelayedByMinutes": 0,
            "MarketState": "Open",
            "PriceTypeBid": "Tradable",
            "PriceTypeAsk": "Tradable",
        },
    }

    normalized = normalize_quote_from_infoprice(item)
    assert normalized["bid"] == 150.25
    assert normalized["ask"] == 150.35
    assert normalized["mid"] == pytest.approx((150.25 + 150.35) / 2)

    dq = derive_data_quality_from_quote(normalized)
    assert dq["is_delayed"] is False
    assert dq["is_indicative"] is False


def test_get_latest_quotes_partial_omission_missing_flag(instruments):
    # Return only the valid instrument; omit invalid from Data to simulate list semantics
    fake_response = {
        "Data": [
            {
                "Uic": 211,
                "LastUpdated": "2025-12-13T08:30:00Z",
                "Quote": {
                    "Bid": 1,
                    "Ask": 2,
                    "Mid": 1.5,
                    "DelayedByMinutes": 0,
                    "MarketState": "Open",
                },
            }
        ]
    }

    rate = {"session": {"remaining": 100, "reset": 10}, "raw_headers": {"X-RateLimit-Session-Remaining": "100"}}

    mock_client = Mock()
    mock_client.get_with_headers.return_value = (fake_response, rate)

    result = get_latest_quotes(instruments, saxo_client=mock_client, include_rate_limit_info=True)

    assert "Stock:211" in result
    assert result["Stock:211"]["quote"]["mid"] == 1.5
    assert result["Stock:211"]["rate_limit_info"]["session"]["remaining"] == 100

    assert "Stock:999999" in result
    assert result["Stock:999999"]["quote"] is None
    assert result["Stock:999999"]["error"]["code"] == "MISSING_FROM_RESPONSE"
    assert result["Stock:999999"]["rate_limit_info"]["session"]["remaining"] == 100


def test_chart_v3_stock_bars_normalization():
    sample = {"Time": "2025-12-13T08:29:00Z", "Open": 1, "High": 2, "Low": 0.5, "Close": 1.5, "Volume": 10}
    bar = normalize_bar_from_chart_sample("Stock", sample)
    assert bar is not None
    assert bar["open"] == 1.0
    assert bar["close"] == 1.5


def test_chart_v3_fx_bid_ask_mid_conversion():
    sample = {
        "Time": "2025-12-13T08:29:00Z",
        "OpenBid": 1.0,
        "OpenAsk": 1.2,
        "HighBid": 1.5,
        "HighAsk": 1.7,
        "LowBid": 0.8,
        "LowAsk": 1.0,
        "CloseBid": 1.1,
        "CloseAsk": 1.3,
    }
    bar = normalize_bar_from_chart_sample("FxSpot", sample)
    assert bar is not None
    assert bar["open"] == pytest.approx(1.1)
    assert bar["close"] == pytest.approx(1.2)


def test_horizon_validation_accepts_supported_values():
    inst = {"asset_type": "Stock", "uic": 211, "symbol": "AAPL"}

    # minimal chart response
    fake_chart = {"Data": []}
    mock_client = Mock()
    mock_client.get_with_headers.return_value = (fake_chart, {})

    for h in SUPPORTED_HORIZON_MINUTES:
        get_ohlc_bars(inst, saxo_client=mock_client, horizon_minutes=h, count=1)


def test_horizon_validation_rejects_unsupported_value():
    inst = {"asset_type": "Stock", "uic": 211, "symbol": "AAPL"}
    mock_client = Mock()

    with pytest.raises(ValueError) as exc:
        get_ohlc_bars(inst, saxo_client=mock_client, horizon_minutes=2, count=1)

    assert "Unsupported Horizon=2" in str(exc.value)


def test_missing_bars_warning_and_returned_count(caplog):
    inst = {"asset_type": "Stock", "uic": 211, "symbol": "AAPL"}

    fake_chart = {
        "Data": [
            {"Time": "2025-12-13T08:29:00Z", "Open": 1, "High": 2, "Low": 0.5, "Close": 1.5},
            {"Time": "2025-12-13T08:30:00Z", "Open": 1.5, "High": 2.5, "Low": 1.0, "Close": 2.0},
        ]
    }
    mock_client = Mock()
    mock_client.get_with_headers.return_value = (fake_chart, {})

    with caplog.at_level("WARNING"):
        out = get_ohlc_bars(inst, saxo_client=mock_client, horizon_minutes=1, count=60)

    assert len(out["bars"]) == 2
    assert out["requested_count"] == 60
    assert out["returned_count"] == 2

    # Freshness uses `now=datetime.now()` internally, so compare with tolerance
    expected = evaluate_bar_freshness(out["bars"], horizon_minutes=1)
    assert out["freshness"]["is_stale"] == expected["is_stale"]
    assert out["freshness"]["reason"] == expected["reason"]
    assert out["freshness"]["age_seconds"] == pytest.approx(expected["age_seconds"], rel=0, abs=0.5)

    assert any("Illiquid/missing bars normal case" in r.message for r in caplog.records)


def test_rate_limit_header_parsing_multi_dimension():
    headers = {
        "X-RateLimit-Session-Remaining": "115",
        "X-RateLimit-Session-Reset": "45",
        "X-RateLimit-AppDay-Remaining": "9500",
        "X-RateLimit-AppDay-Reset": "3600",
    }

    parsed = parse_rate_limit_headers(headers)
    assert parsed["session"]["remaining"] == 115
    assert parsed["session"]["reset"] == 45
    assert parsed["appday"]["remaining"] == 9500
    assert parsed["appday"]["reset"] == 3600


def test_get_latest_quotes_invalid_instrument_emits_error_entry():
    instruments = [
        {"asset_type": "Stock", "uic": 211, "symbol": "AAPL"},
        {"asset_type": "Stock", "symbol": "MISSING_UIC"},
        {"uic": 123, "symbol": "MISSING_ASSET_TYPE"},
        {"asset_type": "Stock", "uic": "NOT_A_NUMBER", "symbol": "BAD_UIC"},
    ]

    fake_response = {
        "Data": [
            {
                "Uic": 211,
                "LastUpdated": "2025-12-13T08:30:00Z",
                "Quote": {"Bid": 1, "Ask": 2, "Mid": 1.5, "DelayedByMinutes": 0, "MarketState": "Open"},
            }
        ]
    }
    mock_client = Mock()
    mock_client.get_with_headers.return_value = (fake_response, {})

    result = get_latest_quotes(instruments, saxo_client=mock_client)

    # Valid key present
    assert "Stock:211" in result

    # Invalid items should not be silently dropped
    invalid_keys = [k for k, v in result.items() if v.get("error", {}).get("code") == "INVALID_INSTRUMENT_INPUT"]
    assert len(invalid_keys) == 3

    # Error containers should preserve identifying information
    for k in invalid_keys:
        assert "original_input" in result[k]
        assert result[k]["quote"] is None


def test_quote_freshness_stale_detection():
    quote = {
        "bid": 1.0,
        "ask": 1.1,
        "mid": 1.05,
        "last_updated": "2025-12-13T08:00:00Z",
        "delayed_by_minutes": 0,
        "market_state": "Open",
    }
    now = datetime(2025, 12, 13, 8, 10, 0, tzinfo=timezone.utc)

    fresh = evaluate_quote_freshness(quote, now=now, stale_quote_seconds=300)
    assert fresh["is_stale"] is True
    assert fresh["reason"] == "STALE_LAST_UPDATED"
