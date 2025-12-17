# Epic 007: Logging and Scheduling System (Saxo-aware)

## 1. Epic Overview

Epic 007 delivers a production-grade, Saxo-aware observability and run-scheduling foundation for **AI-Tradebot**. It standardizes:

1. **Logging**: consistent, auditable, grep-friendly logs with Saxo-critical context fields, safe redaction, and reliable rotation/retention.
2. **Scheduling**: deterministic, non-overlapping execution using OS-native schedulers (systemd timers / cron / Windows Task Scheduler), aligned to `TRADING_HOURS_MODE`, with jitter to reduce API bursts.

This epic does **not** introduce centralized logging, dashboards, or cloud infrastructure. It focuses on a robust local operational baseline that supports debugging, auditing, and safe unattended operation.

---

## 2. Business Value

* **Auditability**: every trade decision and broker-side outcome can be traced by `run_id`, `cycle_id`, `external_reference`, and Saxo identifiers (`ClientKey`, `AccountKey`, `OrderId`, `UIC`, `AssetType`).
* **Operational reliability**: scheduled runs are predictable, non-overlapping, and tolerant of transient errors (with clear post-mortem artifacts).
* **Faster debugging**: consistent log schema allows quick isolation of failures (auth, data, precheck, disclaimers, placement, reconciliation, rate limits).
* **Safety**: enforced redaction reduces accidental leakage of credentials/tokens.

---

## 3. Scope

### 3.1 In Scope

#### Logging

* Standard library `logging` configuration (no external log framework required).
* Console + file logging with rotation and retention (>= 30 days default).
* Saxo-aware log context (fields listed below).
* Safe redaction/masking of secrets and sensitive identifiers.
* Standardized event taxonomy (startup, auth, data, strategy, execution, API errors).
* Optional (recommended) non-blocking logging using `QueueHandler`/`QueueListener`.

#### Scheduling

* OS scheduler runbooks:

  * Linux: systemd timer/service (preferred) and cron (fallback).
  * Windows: Task Scheduler.
* Recommended scheduling strategy: **invoke `main.py --single-cycle`** on a cadence; let the orchestrator enforce `TRADING_HOURS_MODE`.
* Jitter/random delay strategy to spread API load.
* Locking strategy to prevent overlapping runs (critical for cron/Task Scheduler).

### 3.2 Out of Scope

* ELK/Splunk/CloudWatch/etc. centralized logging.
* Dashboards, alerting platforms, paging, real-time monitoring.
* Cloud schedulers (EventBridge, Cloud Scheduler, etc.).
* Full structured JSON logging as the primary log format (see note below).

**Note on JSON**: This epic keeps the main logs as text (key=value). If Epic 006 produces a separate `cycle_summaries.jsonl`, it remains a *telemetry artifact*, not the primary log format.

---

## 4. Constraints and Design Principles

1. **No secrets in logs**: Access tokens, refresh tokens, app secrets, Authorization headers, and full response bodies must never be logged unredacted.
2. **Correlation-first**: every log line must be attributable to:

   * `run_id` (process invocation)
   * `cycle_id` (one trading cycle)
   * and, when applicable, `instrument_id` and `external_reference`/`order_id`
3. **Grep-friendly schema**: human-readable message + `key=value` fields appended consistently.
4. **Fail-closed redaction**: if uncertain whether a field is sensitive, mask it.
5. **Scheduler stability**: prefer OS-native scheduling; avoid a “forever loop daemon” as the only operational model.

---

## 5. Target Architecture

### 5.1 Logging architecture (runtime)

```
main.py
  ├─ setup_logging()  --> console + file handlers (+ optional queue)
  ├─ run_id, cycle_id
  └─ orchestrator cycle
       ├─ market data
       ├─ strategy
       └─ execution
             ├─ precheck
             ├─ disclaimers
             └─ placement/reconciliation

Every component uses:
  get_logger(context) -> LoggerAdapter (or equivalent)
  log_event(event_name, message, **fields)
```

### 5.2 Scheduling architecture (ops)

Preferred: **systemd timer/service** calls:

```
python /path/to/AI-Tradebot/main.py --single-cycle
```

* Prevent overlap via `flock` (cron) or systemd service configuration and lockfile.
* Use jitter at scheduler layer (systemd) or inside the script.

---

## 6. Logging Specification

### 6.1 Log destinations

* **Console**: INFO+ by default.
* **File**: INFO+ by default, rotated daily (or size-based if configured).

Default directory: `./logs/`
Default main file: `./logs/bot.log`

### 6.2 Rotation & retention

Default recommended policy:

* Time-based rotation: daily at midnight (local time or UTC, choose and document).
* Retention: keep **30** rotated files (30 days).

Config options (env vars; names can be finalized during implementation):

* `LOG_DIR=logs`
* `LOG_LEVEL=INFO`
* `LOG_ROTATION_MODE=time|size` (default `time`)
* If `time`: `LOG_RETENTION_DAYS=30`
* If `size`: `LOG_MAX_BYTES=10485760` and `LOG_BACKUP_COUNT=5`

### 6.3 Log format (text + key=value)

**Format template** (example):

```
2025-12-17T07:12:03.214Z | INFO  | execution.trade_executor | precheck_passed |
run_id=... cycle_id=... instrument_id=Stock:211 uic=211 asset_type=Stock
external_reference=ATB-... client_key=*** account_key=*** http_status=200
```

Rules:

* The **message** is short and stable (used as a semantic event label).
* Context is appended as `key=value` tokens.
* Do not rely on JSON; keep it grep-able.

### 6.4 Required correlation fields (always present)

* `run_id` (UUID generated at process start)
* `cycle_id` (monotonic counter or UUID per cycle)
* `mode` (`dry_run=true|false`, `single_cycle=true|false`)
* `env` (`SIM|LIVE`, if known)
* `strategy` (strategy name/version)

Implementation approach:

* A `logging.Filter` ensures these fields exist on every record, with defaults if missing.

### 6.5 Saxo-critical fields (present when applicable)

When an event touches an instrument, request, or order, include as many as relevant:

**Instrument context**

* `instrument_id` = `{AssetType}:{Uic}`
* `asset_type`
* `uic`
* `symbol` (if known)

**Account context**

* `client_key` (masked)
* `account_key` (masked)

**HTTP / API context**

* `http_method`
* `http_url_path` (path only, not full query with secrets)
* `http_status`
* `saxo_request_id` (if returned by Saxo headers; optional)
* `rate_limit_remaining_*` and `rate_limit_reset_*` (if available)

**Execution context**

* `external_reference` (your idempotency/correlation handle)
* `order_id` (Saxo OrderId)
* `precheck_ok` (true/false)
* `disclaimer_required` (true/false)
* `disclaimer_tokens_count`
* `execution_outcome` (SUCCESS / FAILED / SKIPPED / RECONCILIATION_NEEDED)
* `failure_reason` (stable enum-like string)

### 6.6 Redaction and sensitive data handling

Mandatory redaction targets:

* OAuth tokens (access/refresh), app secrets, Authorization headers, cookies.
* Any field matching patterns: `token`, `secret`, `authorization`, `bearer`, `refresh`, `password`.

Masking policy (recommended):

* Keep first 3 and last 2 characters where safe; otherwise full mask.
* Example: `ABCDEF123456` → `ABC***56`
* AccountKey/ClientKey are treated as sensitive (mask by default).

### 6.7 Event taxonomy (minimum required events)

**Startup / config**

* `startup_begin`
* `startup_config_loaded`
* `startup_config_invalid` (fatal)
* `startup_ready`

**Auth**

* `auth_mode_selected`
* `auth_token_refresh_begin`
* `auth_token_refresh_success`
* `auth_token_refresh_failure` (fatal or recoverable depending on mode)

**Cycle**

* `cycle_begin`
* `cycle_skip_outside_trading_hours`
* `cycle_end` (include summary counters)

**Market data**

* `marketdata_fetch_begin`
* `marketdata_fetch_success` (counts)
* `marketdata_fetch_partial` (missing instruments)
* `marketdata_fetch_failure` (recoverable)

**Strategy**

* `strategy_signals_generated` (counts buy/sell/hold)
* `strategy_signal_skipped_insufficient_data` (per instrument where relevant)

**Execution**

* `execution_intent_created`
* `execution_precheck_begin`
* `execution_precheck_passed`
* `execution_precheck_failed`
* `execution_disclaimer_required`
* `execution_disclaimer_resolved`
* `execution_disclaimer_blocked`
* `execution_order_placed`
* `execution_order_rejected`
* `execution_reconcile_begin`
* `execution_reconcile_result`

**Errors**

* `http_error` (status + safe response snippet)
* `unexpected_exception` (stack trace, safe context)

### 6.8 Non-blocking logging (recommended)

If the bot runs frequently or emits high volume logs, use:

* `QueueHandler` in workers
* `QueueListener` to write to file/console in a single thread

This reduces the chance that file I/O delays impact timing-sensitive operations (especially around order placement).

---

## 7. Scheduling Specification

### 7.1 Scheduling strategy (recommended)

* Use OS scheduler to run **one trading cycle per invocation**:

  * `python main.py --single-cycle [--dry-run]`
* Let orchestrator apply `TRADING_HOURS_MODE` gating.
* Benefits:

  * avoids memory leaks / long-running drift
  * isolates crashes to one cycle
  * simplifies restart semantics

### 7.2 Overlap prevention (mandatory)

Overlapping invocations can cause duplicate orders and rate-limit spikes.

Minimum requirement:

* Introduce a lock around execution entrypoint.
  Options:

1. **Linux cron**: use `flock`:

   ```
   * * * * * flock -n /tmp/ai-tradebot.lock python /path/main.py --single-cycle
   ```
2. **systemd**: use a lockfile in `ExecStartPre` or use `flock` in `ExecStart`.
3. **Windows Task Scheduler**: configure “Do not start a new instance” if the task is already running (or emulate lockfile).

### 7.3 Jitter (recommended)

To avoid synchronized bursts against Saxo:

* systemd: `RandomizedDelaySec=15` (or 5–30 seconds depending on interval)
* cron/Windows: implement `--jitter-seconds-max` or an env var `SCHEDULER_JITTER_SECONDS` read by main and applied as a pre-cycle sleep.

### 7.4 Scheduling by `TRADING_HOURS_MODE`

* `always`: schedule continuously at fixed interval (e.g., every 1–5 minutes).
* `fixed`: schedule only during the fixed window **or** schedule broadly and let orchestrator skip outside hours. Recommended: broad schedule + internal gating to reduce scheduler complexity.
* `instrument`: schedule broadly; orchestrator filters instruments by schedule.

### 7.5 Platform runbooks (deliverables)

#### Linux (preferred): systemd

Deliver:

* `docs/runbooks/systemd-ai-tradebot.service`
* `docs/runbooks/systemd-ai-tradebot.timer`

Key characteristics:

* `Restart=on-failure`
* environment file support (e.g., `EnvironmentFile=/path/.env`)
* jitter via timer
* logs to both file and journal (optional)

#### Linux (fallback): cron

Deliver:

* `docs/runbooks/cron.md` with:

  * every-minute example with lock + jitter
  * weekday-only example for equities windows
  * environment loading guidance

#### Windows: Task Scheduler

Deliver:

* `docs/runbooks/windows-task-scheduler.md` with:

  * “repeat task every X minutes for Y hours”
  * “do not start new instance” overlap prevention
  * environment variable setup guidance

---

## 8. Implementation Plan (work items within Epic 007)

### 8.1 Add/extend modules

* `logging_config.py`

  * `setup_logging(...)`
  * `mask_sensitive(...)`
  * `build_log_context(run_id, cycle_id, ...)`
* `log_context.py` (optional)

  * `get_logger(**context) -> LoggerAdapter`
* `runbooks/` docs for schedulers
* Minimal utilities:

  * `scripts/log_tools.py` (optional): grep helpers, order-id extraction patterns

### 8.2 Update call sites to use context consistently

* `main.py` / orchestrator:

  * generate `run_id`, `cycle_id`
  * pass context into market data, strategy, execution
* execution module:

  * ensure it logs `external_reference`, `order_id`, `instrument_id`, and final `execution_outcome`

### 8.3 Add tests

* Unit tests:

  * redaction function masks tokens and keys
  * log formatter includes required fields
  * rotation/retention configured correctly
  * queue logging doesn’t drop messages (if enabled)
* Smoke test:

  * run one cycle (mocked) and assert key events emitted

---

## 9. Success Criteria

Epic 007 is complete when:

1. Logs are written to `logs/` with rotation and >= 30-day retention by default.
2. Every cycle produces clearly correlated logs using `run_id` and `cycle_id`.
3. Saxo-critical identifiers are logged where relevant (instrument/order/request), with masking applied.
4. OAuth refresh, precheck, disclaimer, placement, reconciliation, and HTTP errors are all logged with actionable context.
5. Scheduling runbooks exist for systemd, cron, and Windows Task Scheduler, including:

   * single-cycle invocation
   * overlap prevention
   * jitter recommendation
   * mapping to `TRADING_HOURS_MODE`

---

## 10. Acceptance Criteria (testable)

### Logging

* A new run creates/updates `logs/bot.log`.
* After rotation, old files are retained per policy (default 30 days).
* A log search for a given `external_reference` yields:

  * the intent creation
  * precheck outcome
  * disclaimer result (if any)
  * placement and final execution outcome
* Sensitive values are masked in all log output (validated by unit test).

### Scheduling

* Provided runbooks can be followed to schedule:

  * “every 5 minutes” (always mode)
  * “weekday fixed window” (fixed mode)
* Two concurrent invocations do not overlap (lock proven by documented approach).

---

## 11. Risks and Mitigations

* **Risk: accidental secret leakage**
  Mitigation: central redaction + tests; never log raw headers; safe response snippet truncation.

* **Risk: overlapping runs cause duplicate trades**
  Mitigation: mandatory lockfile strategy in runbooks; Task Scheduler “no new instance.”

* **Risk: log file growth / disk exhaustion**
  Mitigation: rotation + retention defaults; size-based option.

* **Risk: logging overhead affects latency**
  Mitigation: optional QueueHandler; keep DEBUG off by default.

---

## 12. Deliverables

1. Logging configuration module + integration across orchestrator/execution.
2. Default log directory + rotation + retention.
3. Redaction/masking utilities + tests.
4. Runbooks: systemd, cron, Windows Task Scheduler.
5. Minimal log-analysis helpers (optional, but recommended).