# Story 007-003: Scheduling Runbooks & Operational Docs

**Epic:** [Epic 007: Logging and Scheduling System](../../epics/epic-007-logging-and-scheduling.md)
**Status:** Not Started
**Effort:** 3 Story Points
**Priority:** Medium

## User Story
As an **operator**, I want **clear, copy-pasteable configuration files for Systemd, Cron, and Windows Task Scheduler** so that I can **deploy the bot to run reliably in the background with automatic restarts and overlap prevention**.

## Acceptance Criteria
- [ ] `docs/runbooks/systemd-ai-tradebot.service` created.
- [ ] `docs/runbooks/systemd-ai-tradebot.timer` created.
- [ ] `docs/runbooks/cron.md` created with `flock` examples.
- [ ] `docs/runbooks/windows-task-scheduler.md` created.
- [ ] Runbooks explicitly cover:
    - Environment variable loading (`.env` file).
    - Preventing overlapping runs (locking).
    - Adding jitter (random delay) to prevent API spikes.
    - Logging output handling (journald vs file).

## Technical Details

### 1. Systemd (Preferred)

**`ai-tradebot.service`**
```ini
[Unit]
Description=AI Tradebot Single Cycle
After=network.target

[Service]
Type=oneshot
WorkingDirectory=/opt/ai-tradebot
User=tradebot
Group=tradebot
# Load env vars
EnvironmentFile=/opt/ai-tradebot/.env
# Exec
ExecStart=/usr/bin/python3 main.py --single-cycle --config prod
# Jitter is handled by the Timer, but we can also add a pre-sleep here if needed
```

**`ai-tradebot.timer`**
```ini
[Unit]
Description=Run AI Tradebot every 5 minutes

[Timer]
OnBootSec=5min
OnUnitActiveSec=5min
# Jitter to reduce burstiness
RandomizedDelaySec=30
Unit=ai-tradebot.service

[Install]
WantedBy=timers.target
```

### 2. Cron (Fallback)

Documentation must explain `flock` usage:
```bash
# Run every 5 minutes, wait max 10s for lock, fail if locked (prevent overlap)
*/5 * * * * /usr/bin/flock -n /var/lock/ai-tradebot.lock /usr/bin/python3 /opt/ai-tradebot/main.py --single-cycle >> /var/log/ai-tradebot/cron.log 2>&1
```

### 3. Windows Task Scheduler

Documentation must explain:
- Action: Start a Program (`python.exe`)
- Arguments: `main.py --single-cycle`
- Start in: `C:\path\to\repo`
- Settings -> "If the task is already running, then the following rule applies": **"Do not start a new instance"**.

## Dependencies
- None. These are documentation artifacts.

## Validation
- Review the generated files against standard OS syntax.
- (Optional) Verify on a VM if possible, otherwise peer review of syntax is sufficient.
