# Tracehouse

Tracehouse turns your terminal into a searchable memory of how software gets built.

It records commands, terminal output, git context, and AI agent activity, then turns that evidence into a local dashboard you can search later. Use it to reconstruct debugging sessions, review agent behavior, and understand how your workflow changes over time.

## Why Tracehouse

- Remember exactly what happened in the terminal, not just the last command.
- Rebuild debugging sessions from commands, output, and git activity.
- Compare how humans and agents solve the same problems.
- Ask natural-language questions about your work history.
- Keep the data local, private, and under your control.

## Common Uses

- Find when you installed a dependency like CUDA or Docker.
- See which agent fixed a build, auth, or networking issue.
- Review every failed test run in the last month.
- Measure how long a debugging session took from first failure to final fix.
- Understand the command sequences that usually lead to a successful deployment.
- Review what changed across a day, a week, or a specific project.

## What It Captures

- Full command text
- Working directory
- Start and end timestamps
- Duration
- Exit code
- Stdout and stderr
- Shell type
- Host identity
- Session grouping
- Git repository, branch, commit, file changes, and diff summaries
- Human and AI agent activity from supported terminal tools

## What You Get

- Timeline
- Search
- Repositories
- Agents
- Analytics
- Daily reports
- Settings and privacy controls

## Privacy First

- Local-first storage
- Secret detection and redaction
- Exclude directories and command patterns
- Pause and resume capture
- Export and delete controls
- Encrypted backup export

## How To Use It

1. Install the collector hooks.
2. Work normally in your terminal.
3. Let Tracehouse capture commands, outputs, and agent activity.
4. Open the dashboard to search, review, and analyze your work.
5. Ask questions about how a bug was fixed or how a workflow evolved.

## Collector Quick Start

If the collector is already built or installed:

```bash
tracehouse-collector install-hooks
tracehouse-collector uninstall-hooks
tracehouse-collector session-id
```

If you are developing locally:

```bash
cargo run --manifest-path crates/collector/Cargo.toml -- install-hooks
cargo run --manifest-path crates/collector/Cargo.toml -- uninstall-hooks
cargo run --manifest-path crates/collector/Cargo.toml -- session-id
```

## For Developers

- The dashboard lives under `apps/web`.
- The API and local analysis services live under `apps/api`.
- The collector lives under `crates/collector`.

