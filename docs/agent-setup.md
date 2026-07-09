# Tracehouse Agent Setup Guide

Give this file to an AI coding agent when you want Tracehouse installed and
running on your machine.

## Goal

The agent should:

- install the collector
- create the local database
- start the API
- install shell hooks
- start the dashboard
- verify capture
- optionally start the MCP bridge for log analysis

## Assumptions

- The repository is already checked out.
- Rust, Python 3.11+, and Node 20+ are installed.
- The agent has terminal access on the target machine.

## Environment

Use a local Tracehouse state directory and database path so the whole setup
stays self-contained:

```bash
export TRACEHOUSE_COLLECTOR_BIN="tracehouse-collector"
export ABSOLUTELY_API_URL="http://127.0.0.1:8000"
export ABSOLUTELY_DATABASE_PATH="$HOME/.local/share/tracehouse/tracehouse.db"
export ABSOLUTELY_STATE_DIR="$HOME/.local/state/tracehouse"
mkdir -p "$(dirname "$ABSOLUTELY_DATABASE_PATH")" "$ABSOLUTELY_STATE_DIR"
```

If you prefer to work in a Python virtual environment, activate it before the
next step.

## Setup Commands

Run these commands in order. Use separate terminals for the long-running
processes.

```bash
python -m pip install -e apps/api
cargo install --path crates/collector --locked
tracehouse-api init-db "$ABSOLUTELY_DATABASE_PATH"
```

Start the API in one terminal:

```bash
tracehouse-api serve "$ABSOLUTELY_DATABASE_PATH" --host 127.0.0.1 --port 8000
```

Install the shell hooks after the collector binary is available:

```bash
tracehouse-collector install-hooks
```

If you want to preview the profile changes first, run:

```bash
tracehouse-collector install-hooks --dry-run
```

Start the web dashboard in another terminal:

```bash
cd apps/web
npm ci
ABSOLUTELY_API_URL="$ABSOLUTELY_API_URL" npm run dev
```

Optional MCP bridge for Codex or any MCP-capable agent:

```bash
tracehouse-mcp --db "$ABSOLUTELY_DATABASE_PATH"
```

## Verification

Use these checks after setup:

```bash
tracehouse-collector session-id
curl http://127.0.0.1:8000/health
```

Then open the dashboard at `http://127.0.0.1:3000`.

## Notes

- Keep privacy controls enabled.
- Do not switch the setup to cloud sync or remote storage for the MVP.
- If the agent changes anything outside setup, it should explain why before
  proceeding.
