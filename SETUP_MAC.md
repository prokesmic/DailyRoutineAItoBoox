# AI Daily Reader — Mac mini setup

This runs the pipeline locally on your always-on Mac mini via `launchd`. No more Claude Code routines, no more prompt-pasting.

## What changes vs the cloud routine

- **Curation runs via Anthropic API directly** (`run.py` calls `claude-sonnet-4-6` by default).
- **Schedule lives in launchd**, fires daily at 15:00 local time.
- **Secrets live in `.env`** in the project folder, not in a prompt body.
- **No more `git push` from the routine** — `seen.json` and `briefs/` are local state.
- Reads still surface in Readwise Reader on your Boox.

## Prerequisites

- Mac mini set to **Europe/Prague** timezone (`System Settings → General → Date & Time`).
- **Homebrew** installed: `/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"`
- **Python 3.11+**: `brew install python@3.12`
- **Git**: comes with Xcode CLT (`xcode-select --install`)
- **Anthropic API key** with credit on the account (https://console.anthropic.com/settings/keys).
- **Readwise API token** (https://readwise.io/access_token).

## Install (one-time)

```bash
mkdir -p ~/automation
cd ~/automation
git clone https://github.com/prokesmic/DailyRoutineAItoBoox.git ai-daily-reader
cd ai-daily-reader
git checkout claude/create-ai-daily-reader-gylCx

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# Edit .env: paste your ANTHROPIC_API_KEY and READWISE_TOKEN
open -e .env
```

## Test run (foreground, see output)

```bash
cd ~/automation/ai-daily-reader
source .venv/bin/activate
python run.py
```

Expect ~3–7 minutes for a full cycle. Final log line should read like:
```
=== Done. 11 articles + 14 citations + 1 brief. ===
```

Check Readwise Reader (https://read.readwise.io) — you should see the new brief at the top of your inbox, plus the picks and citations.

## Schedule (launchd)

```bash
cd ~/automation/ai-daily-reader
# Substitute your username in the plist template
sed "s/USERNAME/$(whoami)/g" com.prokesmic.aidaily.plist.template > com.prokesmic.aidaily.plist

cp com.prokesmic.aidaily.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.prokesmic.aidaily.plist
```

Verify:
```bash
launchctl list | grep aidaily
# should print: -  0  com.prokesmic.aidaily
```

Run it manually right now (to test the scheduled invocation works):
```bash
launchctl start com.prokesmic.aidaily
tail -f ~/Library/Logs/aidaily-reader.log
```

## Power settings (keep the Mac mini always-on)

`System Settings → Energy`:
- **Prevent automatic sleeping when the display is off**: ON
- **Wake for network access**: ON (so launchd can fire even if display sleeps)
- (Optional) `pmset` from terminal:
  ```bash
  sudo pmset -a sleep 0 disksleep 0 displaysleep 30
  ```
  Sets disk + system to never sleep; display can sleep after 30 min.

## Logs

- Routine output: `~/Library/Logs/aidaily-reader.log`
- Routine errors: `~/Library/Logs/aidaily-reader.error.log`
- Brief HTML archive: `~/automation/ai-daily-reader/briefs/`
- URL ledger: `~/automation/ai-daily-reader/seen.json`

## Updating the code

```bash
cd ~/automation/ai-daily-reader
git pull
# If requirements changed:
source .venv/bin/activate && pip install -r requirements.txt
# launchd picks up new run.py automatically on next scheduled run; no reload needed.
```

## Uninstall

```bash
launchctl unload ~/Library/LaunchAgents/com.prokesmic.aidaily.plist
rm ~/Library/LaunchAgents/com.prokesmic.aidaily.plist
```

## Troubleshooting

- **"ERROR: READWISE_TOKEN and ANTHROPIC_API_KEY must be set"** → check `.env` exists in `~/automation/ai-daily-reader/`, has both keys, no quotes around values.
- **401 from Readwise** → token wrong or expired. Regenerate at https://readwise.io/access_token.
- **Anthropic API errors** → check credit at https://console.anthropic.com/settings/billing.
- **launchd job not firing** → `launchctl list | grep aidaily` to confirm loaded. Check `~/Library/Logs/aidaily-reader.error.log` for stderr.
- **Mac sleeping through scheduled time** → check Energy settings above; for stronger guarantee use `sudo pmset schedule wakeorpoweron MTWRFSU 14:55:00` to wake daily at 14:55.
