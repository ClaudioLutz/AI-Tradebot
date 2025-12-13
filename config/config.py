"""Configuration Module for AI Trading Bot (Saxo Bank)

This module serves as the centralized configuration for the trading bot,
managing API credentials, authentication, watchlists, and trading settings.

All sensitive credentials are loaded from environment variables using python-dotenv.
The module follows security best practices by never hardcoding credentials.

Usage:
    from config.config import Config

    config = Config()
    print(config.base_url)
    print(config.watchlist)

    # Get a valid access token (OAuth auto-refreshes, manual token is static)
    token = config.get_access_token()

    # Resolve UICs for watchlist instruments (queries Saxo API)
    # config.resolve_instruments()
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from dotenv import load_dotenv


class ConfigurationError(Exception):
    """Raised when configuration is invalid or incomplete."""


class Config:
    """Centralized configuration class for the Saxo trading bot.

    Responsibilities:
    - Load configuration from environment (.env via python-dotenv)
    - Support OAuth (recommended) and manual token auth modes
    - Manage structured watchlist entries with {symbol, asset_type, uic}
    - Provide instrument resolution using Saxo /ref/v1/instruments with caching
    - Load and validate trading settings (multi-asset)
    - Provide health checks and safe summaries (no secrets)
    """

    def __init__(self) -> None:
        """Initialize configuration by loading from environment variables.

        Note: Validation runs during initialization and will raise ConfigurationError
        for invalid settings. Some validations (UIC resolution) are only strict in
        LIVE trading mode.
        """
        # Avoid python-dotenv stack inspection issues under pytest/Python 3.13.
        # Explicitly load .env from current working directory.
        load_dotenv(dotenv_path=os.path.join(os.getcwd(), ".env"), override=False)

        # Credentials + auth
        self._load_api_credentials()
        self._initialize_authentication()

        # Watchlist
        self._instrument_cache: Dict[str, Dict[str, Any]] = {}
        self._cache_file = os.getenv("SAXO_INSTRUMENT_CACHE_FILE", ".cache/instruments.json")
        self._load_watchlist()

        # Trading settings
        self._load_trading_settings()

        # Comprehensive validation (Story 002-005)
        self._validate_complete_configuration()

    # ---------------------------------------------------------------------
    # Credentials + Authentication
    # ---------------------------------------------------------------------

    def _load_api_credentials(self) -> None:
        self.base_url = os.getenv("SAXO_REST_BASE")
        if not self.base_url:
            raise ConfigurationError(
                "SAXO_REST_BASE not found in environment variables. "
                "Please configure your .env file with Saxo Bank API base URL."
            )

        self.environment = os.getenv("SAXO_ENV", "SIM").upper()

        # Normalize base URL (remove trailing slash)
        self.base_url = self.base_url.rstrip("/")

        if self.environment not in ["SIM", "LIVE"]:
            raise ConfigurationError(
                f"Invalid SAXO_ENV value: {self.environment}. Must be 'SIM' or 'LIVE'."
            )

        # OAuth credentials (optional)
        self.app_key = os.getenv("SAXO_APP_KEY")
        self.app_secret = os.getenv("SAXO_APP_SECRET")
        self.redirect_uri = os.getenv("SAXO_REDIRECT_URI")

        # Manual token (optional)
        self.manual_access_token = os.getenv("SAXO_ACCESS_TOKEN")

        # Token storage path (OAuth)
        self.token_file = os.getenv("SAXO_TOKEN_FILE", os.path.join(".secrets", "saxo_tokens.json"))

    def _initialize_authentication(self) -> None:
        # Prefer OAuth only when fully configured (app creds + redirect URI).
        # Otherwise fall back to manual token mode if present.
        if self.app_key and self.app_secret and self.redirect_uri:
            self.auth_mode = "oauth"
        elif self.manual_access_token:
            self.auth_mode = "manual"
        else:
            raise ConfigurationError(
                "No valid authentication credentials found. Please configure either:\n"
                "  OAuth Mode (Recommended): SAXO_APP_KEY, SAXO_APP_SECRET, SAXO_REDIRECT_URI\n"
                "  Manual Mode (Testing): SAXO_ACCESS_TOKEN\n"
                "See docs/OAUTH_SETUP_GUIDE.md for details."
            )

    def get_access_token(self) -> str:
        """Get current access token.

        - OAuth mode: uses auth.saxo_oauth.get_access_token() (auto-refresh)
        - Manual mode: returns SAXO_ACCESS_TOKEN
        """
        if self.auth_mode == "manual":
            if not self.manual_access_token:
                raise ConfigurationError("Manual access token not available")
            return self.manual_access_token

        # OAuth mode
        try:
            from auth.saxo_oauth import get_access_token as oauth_get_access_token

            return oauth_get_access_token()
        except Exception as e:
            raise ConfigurationError(
                f"Failed to get OAuth token: {e}. If you haven't authenticated yet, run: python scripts/saxo_login.py"
            )

    def get_masked_token(self) -> str:
        """Get masked token for safe logs."""
        try:
            token = self.get_access_token()
            if not token or len(token) < 12:
                return "****"
            return f"{token[:4]}...{token[-4:]}"
        except Exception:
            return "****"

    def is_simulation(self) -> bool:
        """Return True when running against Saxo's simulation environment.

        Primary source of truth is `SAXO_ENV` (normalized to `self.environment`).
        As a secondary fallback (for misconfigured envs), we infer from the base URL.
        """
        if self.environment == "SIM":
            return True

        # Fallback: infer from common Saxo SIM URL patterns.
        # Use a conservative check to avoid false positives from arbitrary '/sim/' substrings.
        url = (self.base_url or "").lower().rstrip("/")
        return "/sim/openapi" in url or url.endswith("/sim")

    def is_production(self) -> bool:
        return not self.is_simulation()

    def is_oauth_mode(self) -> bool:
        return self.auth_mode == "oauth"

    def is_manual_mode(self) -> bool:
        return self.auth_mode == "manual"

    def get_auth_summary(self) -> Dict[str, Any]:
        summary: Dict[str, Any] = {
            "auth_mode": self.auth_mode,
            "base_url": self.base_url,
            "environment": self.environment,
            "is_simulation": self.is_simulation(),
            "token_masked": self.get_masked_token(),
        }

        if self.auth_mode == "oauth":
            summary["token_file"] = self.token_file
            summary["token_file_exists"] = os.path.exists(self.token_file)
            summary["supports_refresh"] = True
        else:
            summary["supports_refresh"] = False
            summary["expiry_warning"] = "24-hour token limitation"

        return summary

    # ---------------------------------------------------------------------
    # Watchlist + Instrument Resolution
    # ---------------------------------------------------------------------

    def _load_watchlist(self) -> None:
        watchlist_json = os.getenv("WATCHLIST_JSON")
        if watchlist_json:
            try:
                self.watchlist = json.loads(watchlist_json)
            except json.JSONDecodeError as e:
                raise ConfigurationError(f"Invalid WATCHLIST_JSON format: {e}")
        else:
            # Default watchlist: UICs optional; can be resolved later.
            self.watchlist = [
                {"symbol": "AAPL", "asset_type": "Stock", "uic": 211},
                {"symbol": "MSFT", "asset_type": "Stock", "uic": None},
                {"symbol": "GOOGL", "asset_type": "Stock", "uic": None},
                {"symbol": "TSLA", "asset_type": "Stock", "uic": None},
                {"symbol": "AMZN", "asset_type": "Stock", "uic": None},
                {"symbol": "BTCUSD", "asset_type": "FxSpot", "uic": 21700189},
                {"symbol": "ETHUSD", "asset_type": "FxSpot", "uic": 21750301},
            ]

        self._load_instrument_cache()
        self._validate_watchlist_structure()

    def _load_instrument_cache(self) -> None:
        if os.path.exists(self._cache_file):
            try:
                with open(self._cache_file, "r", encoding="utf-8") as f:
                    self._instrument_cache = json.load(f)
            except Exception:
                self._instrument_cache = {}
        else:
            self._instrument_cache = {}

    def _save_instrument_cache(self) -> None:
        os.makedirs(os.path.dirname(self._cache_file), exist_ok=True)
        with open(self._cache_file, "w", encoding="utf-8") as f:
            json.dump(self._instrument_cache, f, indent=2)

    def _validate_watchlist_structure(self) -> None:
        if not isinstance(self.watchlist, list) or not self.watchlist:
            raise ConfigurationError("Watchlist must be a non-empty list")

        valid_asset_types = ["Stock", "Etf", "FxSpot", "FxCrypto", "StockOption"]

        seen = set()
        for idx, inst in enumerate(self.watchlist):
            if not isinstance(inst, dict):
                raise ConfigurationError(f"Watchlist entry {idx} must be a dict")

            if "symbol" not in inst:
                raise ConfigurationError(f"Watchlist entry {idx} missing 'symbol'")
            if "asset_type" not in inst:
                raise ConfigurationError(f"Watchlist entry {idx} missing 'asset_type'")

            symbol = str(inst.get("symbol", "")).strip()
            asset_type = str(inst.get("asset_type", "")).strip()

            if not symbol:
                raise ConfigurationError(f"Watchlist entry {idx} has empty symbol")

            if asset_type not in valid_asset_types:
                raise ConfigurationError(
                    f"Invalid asset_type '{asset_type}' for {symbol}. Must be one of: {', '.join(valid_asset_types)}"
                )

            if "/" in symbol:
                raise ConfigurationError(
                    f"Invalid symbol format '{symbol}': Saxo uses no-slash format. Use 'BTCUSD' not 'BTC/USD'"
                )

            key = (symbol.upper(), asset_type)
            if key in seen:
                raise ConfigurationError(f"Duplicate watchlist instrument: {symbol} ({asset_type})")
            seen.add(key)

    def resolve_instruments(self, force_refresh: bool = False) -> None:
        """Resolve instruments in watchlist to add missing UICs.

        Uses Saxo /ref/v1/instruments and caches results in .cache/instruments.json.
        """

        from data.saxo_client import SaxoClient

        client = SaxoClient()  # uses auth.saxo_oauth.get_access_token internally

        for inst in self.watchlist:
            symbol = inst["symbol"]
            asset_type = inst["asset_type"]
            cache_key = f"{symbol.upper()}_{asset_type}"

            if inst.get("uic") is not None and not force_refresh:
                continue

            if cache_key in self._instrument_cache and not force_refresh:
                cached = self._instrument_cache[cache_key]
                inst["uic"] = cached.get("uic")
                if cached.get("exchange"):
                    inst["exchange"] = cached.get("exchange")
                if cached.get("description"):
                    inst["description"] = cached.get("description")
                continue

            params = {
                "Keywords": symbol,
                "AssetTypes": asset_type,
                "IncludeNonTradable": False,
                "$top": 10,
            }

            response = client.get("/ref/v1/instruments", params=params)
            data = response.get("Data", []) if isinstance(response, dict) else []

            if not data:
                raise ConfigurationError(
                    f"Instrument not found: {symbol} ({asset_type}). Please verify symbol and asset type."
                )

            selected = None
            if len(data) == 1:
                selected = data[0]
            else:
                exact = [d for d in data if str(d.get("Symbol", "")).upper() == symbol.upper()]
                if len(exact) == 1:
                    selected = exact[0]
                else:
                    raise ConfigurationError(
                        f"Ambiguous match for {symbol} ({asset_type}): {len(data)} instruments found. "
                        "Please specify UIC manually in watchlist."
                    )

            uic = selected.get("Uic") or selected.get("Identifier")
            if not uic:
                raise ConfigurationError(f"No UIC found for {symbol} ({asset_type})")

            inst["uic"] = int(uic)
            inst["description"] = selected.get("Description", "")

            exchange = ""
            exchange_info = selected.get("Exchange") or {}
            if isinstance(exchange_info, dict):
                exchange = exchange_info.get("ExchangeId", "")
            if exchange:
                inst["exchange"] = exchange

            self._instrument_cache[cache_key] = {
                "uic": int(uic),
                "description": inst.get("description", ""),
                "exchange": inst.get("exchange", ""),
                "resolved_at": datetime.now().isoformat(),
            }

        self._save_instrument_cache()

    def get_instruments_by_asset_type(self, asset_type: str) -> List[Dict[str, Any]]:
        return [i for i in self.watchlist if i.get("asset_type") == asset_type]

    def get_stock_instruments(self) -> List[Dict[str, Any]]:
        return self.get_instruments_by_asset_type("Stock")

    def get_etf_instruments(self) -> List[Dict[str, Any]]:
        return self.get_instruments_by_asset_type("Etf")

    def get_crypto_instruments(self) -> List[Dict[str, Any]]:
        fxspot = self.get_instruments_by_asset_type("FxSpot")
        fxcrypto = self.get_instruments_by_asset_type("FxCrypto")

        crypto_pairs: List[Dict[str, Any]] = []
        for inst in fxspot:
            sym = str(inst.get("symbol", "")).upper()
            if any(sym.startswith(c) for c in ["BTC", "ETH", "LTC", "XRP", "ADA"]):
                crypto_pairs.append(inst)

        return crypto_pairs + fxcrypto

    def get_instrument_by_symbol(self, symbol: str, asset_type: Optional[str] = None) -> Optional[Dict[str, Any]]:
        for inst in self.watchlist:
            if str(inst.get("symbol", "")).upper() == symbol.upper():
                if asset_type is None or inst.get("asset_type") == asset_type:
                    return inst
        return None

    def add_instrument(self, symbol: str, asset_type: str, uic: Optional[int] = None) -> None:
        symbol = str(symbol or "").strip()
        if "/" in symbol:
            raise ConfigurationError(
                f"Invalid symbol format '{symbol}': Saxo uses no-slash format (e.g. BTCUSD)."
            )

        existing = self.get_instrument_by_symbol(symbol, asset_type)
        if existing:
            raise ConfigurationError(f"Instrument already in watchlist: {symbol} ({asset_type})")

        self.watchlist.append({"symbol": symbol.upper(), "asset_type": asset_type, "uic": uic})

        if uic is None:
            self.resolve_instruments()

    def remove_instrument(self, symbol: str, asset_type: Optional[str] = None) -> None:
        inst = self.get_instrument_by_symbol(symbol, asset_type)
        if not inst:
            raise ConfigurationError(f"Instrument not found in watchlist: {symbol}")
        self.watchlist.remove(inst)

    def get_watchlist_summary(self) -> Dict[str, Any]:
        resolved_count = sum(1 for i in self.watchlist if i.get("uic") is not None)
        return {
            "total_instruments": len(self.watchlist),
            "resolved": resolved_count,
            "unresolved": len(self.watchlist) - resolved_count,
            "by_asset_type": {
                "Stock": len(self.get_stock_instruments()),
                "Etf": len(self.get_etf_instruments()),
                "Crypto": len(self.get_crypto_instruments()),
            },
            "instruments": [
                {
                    "symbol": i.get("symbol"),
                    "asset_type": i.get("asset_type"),
                    "uic": i.get("uic"),
                    "resolved": i.get("uic") is not None,
                }
                for i in self.watchlist
            ],
        }

    # ---------------------------------------------------------------------
    # Trading Settings
    # ---------------------------------------------------------------------

    def _load_trading_settings(self) -> None:
        self.default_timeframe = os.getenv("DEFAULT_TIMEFRAME", "1Min")
        self.data_lookback_days = int(os.getenv("DATA_LOOKBACK_DAYS", "30"))

        self.dry_run = os.getenv("DRY_RUN", "True").lower() in ["true", "1", "yes"]
        self.backtest_mode = os.getenv("BACKTEST_MODE", "False").lower() in ["true", "1", "yes"]

        self.max_position_value_usd = float(os.getenv("MAX_POSITION_VALUE_USD", "1000.0"))
        self.max_fx_notional = float(os.getenv("MAX_FX_NOTIONAL", "10000.0"))

        # Backward compatibility alias
        self.max_position_size = self.max_position_value_usd

        self.max_portfolio_exposure = float(os.getenv("MAX_PORTFOLIO_EXPOSURE", "10000.0"))

        self.stop_loss_pct = float(os.getenv("STOP_LOSS_PCT", "2.0"))
        self.take_profit_pct = float(os.getenv("TAKE_PROFIT_PCT", "5.0"))

        self.min_trade_amount = float(os.getenv("MIN_TRADE_AMOUNT", "100.0"))
        self.max_trades_per_day = int(os.getenv("MAX_TRADES_PER_DAY", "10"))

        self.trading_hours_mode = os.getenv("TRADING_HOURS_MODE", "fixed").lower()

        self._parse_trading_hours()
        self._validate_trading_settings()

    def _parse_trading_hours(self) -> None:
        open_time_str = os.getenv("MARKET_OPEN_TIME", os.getenv("MARKET_OPEN_HOUR", "14:30"))
        close_time_str = os.getenv("MARKET_CLOSE_TIME", os.getenv("MARKET_CLOSE_HOUR", "21:00"))

        def parse_time(time_str: str) -> Tuple[int, int]:
            s = str(time_str).strip()
            if ":" in s:
                h, m = s.split(":", 1)
                return int(h), int(m)
            return int(s), 0

        self.market_open_hour, self.market_open_minute = parse_time(open_time_str)
        self.market_close_hour, self.market_close_minute = parse_time(close_time_str)

        self.market_open_minutes = self.market_open_hour * 60 + self.market_open_minute
        self.market_close_minutes = self.market_close_hour * 60 + self.market_close_minute

        self.log_level = os.getenv("LOG_LEVEL", "INFO")
        self.enable_notifications = os.getenv("ENABLE_NOTIFICATIONS", "False").lower() in ["true", "1", "yes"]

    def _validate_trading_settings(self) -> None:
        valid_timeframes = ["1Min", "5Min", "15Min", "30Min", "1Hour", "4Hour", "1Day"]
        if self.default_timeframe not in valid_timeframes:
            raise ConfigurationError(
                f"Invalid timeframe: {self.default_timeframe}. Must be one of: {', '.join(valid_timeframes)}"
            )

        if self.stop_loss_pct <= 0 or self.stop_loss_pct > 100:
            raise ConfigurationError(
                f"Invalid stop_loss_pct: {self.stop_loss_pct}. Must be between 0 and 100."
            )

        if self.take_profit_pct <= 0 or self.take_profit_pct > 1000:
            raise ConfigurationError(
                f"Invalid take_profit_pct: {self.take_profit_pct}. Must be between 0 and 1000."
            )

        if self.max_position_value_usd <= 0:
            raise ConfigurationError(
                f"Invalid max_position_value_usd: {self.max_position_value_usd}. Must be positive."
            )

        if self.max_fx_notional <= 0:
            raise ConfigurationError(f"Invalid max_fx_notional: {self.max_fx_notional}. Must be positive.")

        if self.max_portfolio_exposure <= 0:
            raise ConfigurationError(
                f"Invalid max_portfolio_exposure: {self.max_portfolio_exposure}. Must be positive."
            )

        if self.min_trade_amount <= 0:
            raise ConfigurationError(f"Invalid min_trade_amount: {self.min_trade_amount}. Must be positive.")

        valid_modes = ["fixed", "always", "instrument"]
        if self.trading_hours_mode not in valid_modes:
            raise ConfigurationError(
                f"Invalid trading_hours_mode: {self.trading_hours_mode}. Must be one of: {', '.join(valid_modes)}"
            )

        if self.trading_hours_mode == "fixed":
            if not (0 <= self.market_open_hour < 24):
                raise ConfigurationError(
                    f"Invalid market_open_hour: {self.market_open_hour}. Must be 0-23."
                )
            if not (0 <= self.market_close_hour < 24):
                raise ConfigurationError(
                    f"Invalid market_close_hour: {self.market_close_hour}. Must be 0-23."
                )

        valid_log_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if self.log_level.upper() not in valid_log_levels:
            raise ConfigurationError(
                f"Invalid log_level: {self.log_level}. Must be one of: {', '.join(valid_log_levels)}"
            )

    def get_position_size_for_asset(self, instrument: Dict[str, Any], price: float, risk_pct: float = 1.0) -> float:
        asset_type = instrument.get("asset_type")

        if asset_type in ["Stock", "Etf"]:
            value_usd = self.max_position_value_usd * (risk_pct / 100.0)
            return min(value_usd, self.max_portfolio_exposure)

        if asset_type in ["FxSpot", "FxCrypto"]:
            notional = self.max_fx_notional * (risk_pct / 100.0)
            return min(notional, self.max_portfolio_exposure)

        raise ConfigurationError(
            f"Unsupported asset type: {asset_type}. Supported: Stock, Etf, FxSpot, FxCrypto"
        )

    def calculate_shares_for_stock(self, price: float, risk_pct: float = 1.0) -> int:
        value_usd = self.max_position_value_usd * (risk_pct / 100.0)
        value_usd = min(value_usd, self.max_portfolio_exposure)
        shares = int(value_usd / price)
        return max(shares, 1)

    def is_dry_run(self) -> bool:
        return self.dry_run

    def is_backtest_mode(self) -> bool:
        return self.backtest_mode

    def is_live_trading(self) -> bool:
        return not self.dry_run and not self.backtest_mode

    def get_trading_mode(self) -> str:
        if self.backtest_mode:
            return "BACKTEST"
        if self.dry_run:
            return "DRY_RUN"
        return "LIVE"

    def is_within_trading_hours(self, current_hour: Optional[int] = None, current_minute: Optional[int] = None) -> bool:
        from datetime import datetime as _dt

        now = _dt.utcnow()
        if current_hour is None:
            current_hour = now.hour
        if current_minute is None:
            current_minute = now.minute

        current_minutes = current_hour * 60 + current_minute

        if self.market_open_minutes <= self.market_close_minutes:
            return self.market_open_minutes <= current_minutes < self.market_close_minutes

        return current_minutes >= self.market_open_minutes or current_minutes < self.market_close_minutes

    def is_trading_allowed(
        self,
        instrument: Dict[str, Any],
        current_hour: Optional[int] = None,
        current_minute: Optional[int] = None,
        current_weekday: Optional[int] = None,
    ) -> bool:
        from datetime import datetime as _dt

        now = _dt.utcnow()
        if current_hour is None:
            current_hour = now.hour
        if current_minute is None:
            current_minute = now.minute
        if current_weekday is None:
            current_weekday = now.weekday()

        if self.trading_hours_mode == "always":
            return True

        if self.trading_hours_mode == "fixed":
            return self.is_within_trading_hours(current_hour, current_minute)

        if self.trading_hours_mode == "instrument":
            asset_type = instrument.get("asset_type")
            if asset_type in ["FxSpot", "FxCrypto"]:
                return current_weekday < 5
            if asset_type in ["Stock", "Etf"]:
                return self.is_within_trading_hours(current_hour, current_minute)
            return False

        return False

    def get_trading_settings_summary(self) -> Dict[str, Any]:
        trading_hours = (
            f"{self.market_open_hour:02d}:{self.market_open_minute:02d}-{self.market_close_hour:02d}:{self.market_close_minute:02d} UTC"
            if self.trading_hours_mode == "fixed"
            else self.trading_hours_mode
        )
        return {
            "trading_mode": self.get_trading_mode(),
            "default_timeframe": self.default_timeframe,
            "dry_run": self.dry_run,
            "backtest_mode": self.backtest_mode,
            "max_position_value_usd": self.max_position_value_usd,
            "max_fx_notional": self.max_fx_notional,
            "max_portfolio_exposure": self.max_portfolio_exposure,
            "stop_loss_pct": self.stop_loss_pct,
            "take_profit_pct": self.take_profit_pct,
            "min_trade_amount": self.min_trade_amount,
            "max_trades_per_day": self.max_trades_per_day,
            "trading_hours_mode": self.trading_hours_mode,
            "trading_hours": trading_hours,
            "log_level": self.log_level,
        }

    # ---------------------------------------------------------------------
    # Validation + Health
    # ---------------------------------------------------------------------

    def is_valid(self) -> bool:
        try:
            self._validate_complete_configuration()
            return True
        except ConfigurationError:
            return False

    def _validate_auth_mode(self) -> None:
        if self.auth_mode == "oauth":
            if not self.app_key or not self.app_secret or not self.redirect_uri:
                raise ConfigurationError(
                    "OAuth mode detected but app credentials incomplete. Required: SAXO_APP_KEY, SAXO_APP_SECRET, SAXO_REDIRECT_URI"
                )
            if not os.path.exists(self.token_file):
                raise ConfigurationError(
                    f"OAuth mode configured but token file not found: {self.token_file}\n"
                    "Please authenticate first:\n  python scripts/saxo_login.py"
                )
        elif self.auth_mode == "manual":
            if not self.manual_access_token:
                raise ConfigurationError("Manual token mode detected but SAXO_ACCESS_TOKEN not set.")
        else:
            raise ConfigurationError(f"Unknown auth mode: {self.auth_mode}")

    def _validate_instrument_resolution(self, strict: Optional[bool] = None) -> None:
        unresolved = [i for i in self.watchlist if i.get("uic") is None]
        if not unresolved:
            return

        if strict is None:
            strict = self.is_live_trading()

        symbols = ", ".join(str(i.get("symbol", "?")) for i in unresolved)
        msg = (
            f"Unresolved instruments found: {symbols}\n"
            "Run config.resolve_instruments() to query Saxo API for UICs, or specify UICs manually in WATCHLIST_JSON/default watchlist."
        )

        if strict:
            raise ConfigurationError(msg)

    def _validate_crypto_asset_types(self) -> None:
        crypto_prefixes = ("BTC", "ETH", "LTC", "XRP", "ADA")
        crypto = [i for i in self.watchlist if str(i.get("symbol", "")).upper().startswith(crypto_prefixes)]
        for inst in crypto:
            at = inst.get("asset_type")
            if at not in ["FxSpot", "FxCrypto"]:
                raise ConfigurationError(
                    f"Crypto instrument {inst.get('symbol')} has invalid asset type: {at}. Expected FxSpot or FxCrypto."
                )

    def _validate_crypto_symbol_format(self) -> None:
        bad = [
            str(i.get("symbol"))
            for i in self.watchlist
            if i.get("asset_type") in ["FxSpot", "FxCrypto"] and "/" in str(i.get("symbol", ""))
        ]
        if bad:
            raise ConfigurationError(
                f"Crypto symbols contain slashes (invalid for Saxo): {', '.join(bad)}. Use BTCUSD/ETHUSD (no slashes)."
            )

    def _validate_complete_configuration(self) -> None:
        self._validate_auth_mode()
        self._validate_watchlist_structure()
        self._validate_crypto_asset_types()
        self._validate_crypto_symbol_format()
        self._validate_instrument_resolution(strict=None)

        if self.min_trade_amount > self.max_position_value_usd:
            raise ConfigurationError(
                f"min_trade_amount (${self.min_trade_amount}) cannot exceed max_position_value_usd (${self.max_position_value_usd})"
            )

        if self.max_position_value_usd > self.max_portfolio_exposure:
            raise ConfigurationError(
                f"max_position_value_usd (${self.max_position_value_usd}) cannot exceed max_portfolio_exposure (${self.max_portfolio_exposure})"
            )

    def validate_symbol(self, symbol: str) -> bool:
        if not symbol or not isinstance(symbol, str):
            return False
        if "/" in symbol:
            return False
        if not all(c.isalnum() or c in ["-", "."] for c in symbol):
            return False
        return 1 <= len(symbol) <= 20

    def get_configuration_health(self) -> Dict[str, Any]:
        health: Dict[str, Any] = {"overall_valid": self.is_valid(), "sections": {}}

        # API credentials
        try:
            token_ok = bool(self.get_access_token())
            health["sections"]["api_credentials"] = {
                "valid": bool(self.base_url and token_ok),
                "base_url_set": bool(self.base_url),
                "auth_mode": self.auth_mode,
                "token_set": token_ok,
                "environment": self.environment,
            }
        except Exception as e:
            health["sections"]["api_credentials"] = {"valid": False, "error": str(e)}

        # Watchlist
        try:
            unresolved = sum(1 for inst in self.watchlist if inst.get("uic") is None)
            health["sections"]["watchlist"] = {
                "valid": len(self.watchlist) > 0 and unresolved == 0,
                "instrument_count": len(self.watchlist),
                "resolved_count": len(self.watchlist) - unresolved,
                "unresolved_count": unresolved,
                "has_crypto": any(inst.get("asset_type") in ["FxSpot", "FxCrypto"] for inst in self.watchlist),
            }
        except Exception as e:
            health["sections"]["watchlist"] = {"valid": False, "error": str(e)}

        # Trading settings
        try:
            rr = round(self.take_profit_pct / self.stop_loss_pct, 2) if self.stop_loss_pct > 0 else 0
            health["sections"]["trading_settings"] = {
                "valid": True,
                "trading_mode": self.get_trading_mode(),
                "dry_run": self.dry_run,
                "timeframe": self.default_timeframe,
                "trading_hours_mode": self.trading_hours_mode,
                "risk_reward_ratio": rr,
            }
        except Exception as e:
            health["sections"]["trading_settings"] = {"valid": False, "error": str(e)}

        return health

    def print_configuration_summary(self) -> None:
        print("=" * 60)
        print("Trading Bot Configuration Summary")
        print("=" * 60)
        print("\nAPI:")
        print(f"  Environment: {self.environment}")
        print(f"  Auth Mode:   {self.auth_mode}")
        print(f"  Base URL:    {self.base_url}")
        print(f"  Token:       {self.get_masked_token()}")

        print("\nWatchlist:")
        wl = self.get_watchlist_summary()
        print(f"  Total: {wl['total_instruments']} | Resolved: {wl['resolved']} | Unresolved: {wl['unresolved']}")

        print("\nTrading Settings:")
        ts = self.get_trading_settings_summary()
        print(f"  Mode:      {ts['trading_mode']}")
        print(f"  Timeframe: {ts['default_timeframe']}")
        print(f"  Hours:     {ts['trading_hours']}")

    def export_configuration(self, include_sensitive: bool = False) -> Dict[str, Any]:
        return {
            "api": {
                "base_url": self.base_url,
                "auth_mode": self.auth_mode,
                "environment": self.environment,
                "token": self.get_access_token() if include_sensitive else self.get_masked_token(),
                "is_simulation": self.is_simulation(),
            },
            "watchlist": {"instruments": self.watchlist, "count": len(self.watchlist)},
            "trading_settings": {
                "timeframe": self.default_timeframe,
                "data_lookback_days": self.data_lookback_days,
                "trading_mode": self.get_trading_mode(),
                "dry_run": self.dry_run,
                "backtest_mode": self.backtest_mode,
                "trading_hours_mode": self.trading_hours_mode,
            },
            "risk_management": {
                "max_position_value_usd": self.max_position_value_usd,
                "max_fx_notional": self.max_fx_notional,
                "max_portfolio_exposure": self.max_portfolio_exposure,
                "stop_loss_pct": self.stop_loss_pct,
                "take_profit_pct": self.take_profit_pct,
                "min_trade_amount": self.min_trade_amount,
            },
            "logging": {"log_level": self.log_level, "enable_notifications": self.enable_notifications},
        }

    def save_configuration_to_file(self, filepath: str, include_sensitive: bool = False) -> None:
        cfg = self.export_configuration(include_sensitive=include_sensitive)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)

    def get_summary(self) -> Dict[str, Any]:
        return {
            "base_url": self.base_url,
            "auth_mode": self.auth_mode,
            "environment": self.environment,
            "token_masked": self.get_masked_token(),
            "is_simulation": self.is_simulation(),
            "watchlist": self.get_watchlist_summary(),
            "trading_settings": self.get_trading_settings_summary(),
        }


def get_config() -> Config:
    """Get a configured Config instance.

    Raises:
        ConfigurationError: if configuration is invalid.
    """

    config = Config()
    if not config.is_valid():
        raise ConfigurationError("Configuration validation failed")
    return config


__all__ = ["Config", "ConfigurationError", "get_config"]
