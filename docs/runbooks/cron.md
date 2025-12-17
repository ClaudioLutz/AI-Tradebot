# Cron Scheduling for AI-Tradebot

If Systemd is not available, you can use `cron` to schedule the bot.

**Important:** You MUST use `flock` to prevent overlapping executions.

## 1. Prerequisites

Ensure `flock` is installed:
```bash
sudo apt-get install util-linux
```

## 2. Crontab Configuration

Open crontab:
```bash
crontab -e
```

### Example: Run every 5 minutes

```bash
# Run every 5 minutes, wait max 10s for lock, fail if locked (prevent overlap)
*/5 * * * * /usr/bin/flock -n /var/lock/ai-tradebot.lock /usr/bin/python3 /opt/ai-tradebot/main.py --single-cycle >> /var/log/ai-tradebot/cron.log 2>&1
```

### Example: Run only on Weekdays (Monday-Friday)

```bash
# Run every 5 minutes, Mon-Fri
*/5 * * * 1-5 /usr/bin/flock -n /var/lock/ai-tradebot.lock /usr/bin/python3 /opt/ai-tradebot/main.py --single-cycle >> /var/log/ai-tradebot/cron.log 2>&1
```

### Adding Jitter (Random Delay)

To add jitter (e.g., up to 30 seconds delay) to avoid synchronized bursts:

```bash
# Sleep random 0-30s before starting
*/5 * * * * sleep $((RANDOM \% 30)) && /usr/bin/flock -n /var/lock/ai-tradebot.lock /usr/bin/python3 /opt/ai-tradebot/main.py --single-cycle >> /var/log/ai-tradebot/cron.log 2>&1
```

## 3. Environment Variables

Cron does not load your shell environment. You should either:

1. Use absolute paths (as shown above).
2. Load the `.env` file explicitly in the command:

```bash
*/5 * * * * set -a; source /opt/ai-tradebot/.env; set +a; /usr/bin/flock ...
```
