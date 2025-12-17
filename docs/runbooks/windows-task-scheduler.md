# Windows Task Scheduler for AI-Tradebot

For Windows environments, use **Task Scheduler** to run the bot periodically.

## 1. Create a Basic Task

1. Open **Task Scheduler**.
2. Click **Create Task** (not Basic Task).
3. **General** tab:
   - Name: `AI Tradebot`
   - Security options: "Run whether user is logged on or not" (requires password) or "Run only when user is logged on".
   - "Run with highest privileges" (optional, depending on file permissions).

## 2. Triggers (Scheduling)

1. **Triggers** tab -> **New**.
2. Begin the task: **On a schedule**.
3. Settings: **Daily**.
4. Start: Today's date, time (e.g., 09:30:00).
5. **Advanced settings**:
   - Check **Repeat task every**: `5 minutes`.
   - **for a duration of**: `Indefinitely` (or `12 hours` if you only want trading hours).
   - Check **Enabled**.

## 3. Actions (Execution)

1. **Actions** tab -> **New**.
2. Action: **Start a program**.
3. Program/script: `python.exe` (use full path if not in PATH, e.g., `C:\Python39\python.exe`).
4. Add arguments: `main.py --single-cycle`
5. Start in: `C:\path\to\ai-tradebot` (Directory containing `main.py`).

## 4. Overlap Prevention (Critical)

To prevent multiple instances from running simultaneously:

1. **Settings** tab.
2. Look for **"If the task is already running, then the following rule applies:"**.
3. Select: **"Do not start a new instance"**.

## 5. Environment Variables

Task Scheduler does not automatically load variables from `.env` unless your script loads them (which `main.py` does via `python-dotenv`).

Ensure your `.env` file is in the "Start in" directory.

## 6. Jitter (Random Delay)

Windows Task Scheduler has a "Random delay" feature, but it is often for "daily" triggers, not minute repetitions.

To implement jitter, create a wrapper batch script `run_bot.bat`:

```batch
@echo off
rem Sleep for random 0-30 seconds
set /a delay=%random% %% 30
timeout /t %delay% /nobreak

cd C:\path\to\ai-tradebot
python main.py --single-cycle
```

Then point the Task Action to `run_bot.bat` instead of `python.exe`.
