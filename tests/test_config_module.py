"""Comprehensive tests for config/config.py module.

Tests cover:
- Configuration initialization
- Credentials loading
- Watchlist management
- Trading settings
- Validation logic
- Export functionality

NOTE: Tests are designed to be deterministic by patching os.environ.
"""

import json
import os
import tempfile
from unittest.mock import mock_open, patch

import pytest

from config.config import Config, ConfigurationError, get_config


@pytest.fixture
def base_manual_env():
    return {
        "SAXO_REST_BASE": "https://gateway.saxobank.com/sim/openapi",
        "SAXO_ACCESS_TOKEN": "test_manual_token_12345678901234567890",
        "SAXO_ENV": "SIM",
        "DRY_RUN": "True",
        # Ensure manual mode is selected deterministically
        "SAXO_APP_KEY": "",
        "SAXO_APP_SECRET": "",
        "SAXO_REDIRECT_URI": "",
    }


@pytest.fixture
def base_oauth_env():
    return {
        "SAXO_REST_BASE": "https://gateway.saxobank.com/sim/openapi",
        "SAXO_APP_KEY": "test_app_key",
        "SAXO_APP_SECRET": "test_app_secret",
        "SAXO_REDIRECT_URI": "http://localhost:8765/callback",
        "SAXO_ENV": "SIM",
        "DRY_RUN": "True",
    }


class TestConfigInitialization:
    def test_config_initialization_success_manual(self, base_manual_env):
        with patch.dict(os.environ, base_manual_env, clear=True):
            cfg = Config()
            assert cfg.base_url
            assert cfg.auth_mode == "manual"
            assert isinstance(cfg.watchlist, list)
            assert cfg.default_timeframe

    def test_missing_base_url_raises(self):
        # Config explicitly loads .env from CWD; prevent that from mutating environment.
        with patch.dict(os.environ, {}, clear=True):
            with patch("dotenv.main.DotEnv.set_as_environment_variables", return_value=True):
                with pytest.raises(ConfigurationError) as exc:
                    Config()
            assert "SAXO_REST_BASE" in str(exc.value)

    def test_no_credentials_raises(self):
        # Prevent .env from mutating environment.
        with patch.dict(os.environ, {"SAXO_REST_BASE": "https://gateway.saxobank.com/sim/openapi"}, clear=True):
            with patch("dotenv.main.DotEnv.set_as_environment_variables", return_value=True):
                with pytest.raises(ConfigurationError) as exc:
                    Config()
            assert "No valid authentication credentials" in str(exc.value)


class TestAuthentication:
    def test_manual_mode_detection(self, base_manual_env):
        with patch.dict(os.environ, base_manual_env, clear=True):
            cfg = Config()
            assert cfg.is_manual_mode()
            assert cfg.get_access_token() == base_manual_env["SAXO_ACCESS_TOKEN"]
            assert cfg.is_simulation() is True

    def test_auth_conflict_both_configured_raises(self, base_oauth_env):
        # Issue B from Epic 002 review: prevent auth conflict when both modes are set
        env = dict(base_oauth_env)
        env["SAXO_ACCESS_TOKEN"] = "test_manual_token_12345678901234567890"
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(ConfigurationError) as exc:
                Config()
            assert "conflict" in str(exc.value).lower()
            assert "choose ONE" in str(exc.value) or "one authentication mode" in str(exc.value).lower()

    def test_is_simulation_false_in_live_env(self, base_manual_env):
        env = dict(base_manual_env)
        env["SAXO_ENV"] = "LIVE"
        env["SAXO_REST_BASE"] = "https://gateway.saxobank.com/openapi"  # no /sim/ marker
        with patch.dict(os.environ, env, clear=True):
            cfg = Config()
            assert cfg.is_simulation() is False
            assert cfg.is_production() is True

    def test_is_simulation_fallback_detects_sim_from_base_url(self, base_manual_env):
        env = dict(base_manual_env)
        env["SAXO_ENV"] = "LIVE"  # misconfigured env
        env["SAXO_REST_BASE"] = "https://gateway.saxobank.com/sim/openapi"
        with patch.dict(os.environ, env, clear=True):
            cfg = Config()
            assert cfg.is_simulation() is True

    def test_oauth_mode_detection_requires_token_file(self, base_oauth_env):
        # config validates token file exists in OAuth mode
        with patch.dict(os.environ, base_oauth_env, clear=True):
            with patch("os.path.exists", return_value=False):
                with pytest.raises(ConfigurationError) as exc:
                    Config()
                assert "token file" in str(exc.value).lower()

    def test_oauth_mode_get_access_token_delegates(self, base_oauth_env):
        with patch.dict(os.environ, base_oauth_env, clear=True):
            with patch("os.path.exists", return_value=True):
                # auth.saxo_oauth reads from its own TOKEN_PATH (fixed) - mock open
                with patch("builtins.open", mock_open(read_data=json.dumps({"access_token": "abc", "access_token_expires_at": 9999999999}))):
                    with patch("auth.saxo_oauth.get_access_token", return_value="oauth_token"):
                        cfg = Config()
                        assert cfg.is_oauth_mode()
                        assert cfg.get_access_token() == "oauth_token"


class TestWatchlist:
    def test_default_watchlist_structure(self, base_manual_env):
        with patch.dict(os.environ, base_manual_env, clear=True):
            cfg = Config()
            assert cfg.watchlist
            first = cfg.watchlist[0]
            assert "symbol" in first
            assert "asset_type" in first
            assert "uic" in first

    def test_watchlist_json_override(self, base_manual_env):
        wl = [{"symbol": "AAPL", "asset_type": "Stock", "uic": 211}]
        env = dict(base_manual_env)
        env["WATCHLIST_JSON"] = json.dumps(wl)
        with patch.dict(os.environ, env, clear=True):
            cfg = Config()
            assert cfg.watchlist == wl

    def test_crypto_symbol_slash_rejected(self, base_manual_env):
        wl = [{"symbol": "BTC/USD", "asset_type": "FxSpot", "uic": 1}]
        env = dict(base_manual_env)
        env["WATCHLIST_JSON"] = json.dumps(wl)
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(ConfigurationError) as exc:
                Config()
            assert "no-slash" in str(exc.value).lower() or "slash" in str(exc.value).lower()

    def test_validate_symbol(self, base_manual_env):
        with patch.dict(os.environ, base_manual_env, clear=True):
            cfg = Config()
            assert cfg.validate_symbol("AAPL")
            assert cfg.validate_symbol("BTCUSD")
            assert not cfg.validate_symbol("BTC/USD")
            assert not cfg.validate_symbol("ABC@123")


class TestTradingSettings:
    def test_default_settings(self, base_manual_env):
        with patch.dict(os.environ, base_manual_env, clear=True):
            cfg = Config()
            assert cfg.default_timeframe == "1Min"
            assert cfg.dry_run is True
            assert cfg.max_position_value_usd == 1000.0
            assert cfg.max_fx_notional == 10000.0

    def test_invalid_timeframe_raises(self, base_manual_env):
        env = dict(base_manual_env)
        env["DEFAULT_TIMEFRAME"] = "BadFrame"
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(ConfigurationError) as exc:
                Config()
            assert "Invalid timeframe" in str(exc.value)

    def test_trading_hours_modes(self, base_manual_env):
        env = dict(base_manual_env)
        env["TRADING_HOURS_MODE"] = "always"
        with patch.dict(os.environ, env, clear=True):
            cfg = Config()
            inst = {"symbol": "BTCUSD", "asset_type": "FxSpot", "uic": 1}
            assert cfg.is_trading_allowed(inst, current_hour=3, current_weekday=6)


class TestValidation:
    def test_cross_validation_min_trade_gt_max_position_fails(self, base_manual_env):
        env = dict(base_manual_env)
        env["MIN_TRADE_AMOUNT"] = "2000"
        env["MAX_POSITION_VALUE_USD"] = "1000"
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(ConfigurationError) as exc:
                Config()
            assert "min_trade_amount" in str(exc.value)


class TestExport:
    def test_export_masks_token(self, base_manual_env):
        with patch.dict(os.environ, base_manual_env, clear=True):
            cfg = Config()
            exported = cfg.export_configuration(include_sensitive=False)
            assert "..." in exported["api"]["token"]

    def test_save_configuration_to_file(self, base_manual_env):
        with patch.dict(os.environ, base_manual_env, clear=True):
            cfg = Config()
            with tempfile.NamedTemporaryFile(delete=False, suffix=".json") as f:
                path = f.name
            try:
                cfg.save_configuration_to_file(path, include_sensitive=False)
                assert os.path.exists(path)
            finally:
                if os.path.exists(path):
                    os.remove(path)


class TestGetConfig:
    def test_get_config_success(self, base_manual_env):
        with patch.dict(os.environ, base_manual_env, clear=True):
            cfg = get_config()
            assert isinstance(cfg, Config)

    def test_get_config_invalid_raises(self):
        with patch.dict(os.environ, {}, clear=True):
            with patch("dotenv.main.DotEnv.set_as_environment_variables", return_value=True):
                with pytest.raises(ConfigurationError):
                    get_config()
