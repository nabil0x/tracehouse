# Tracehouse

Tracehouse is a local-first terminal intelligence platform for reconstructing how development work happened from terminal commands, git activity, file changes, and AI agent sessions.

## What It Does

- Captures shell commands, stdout, stderr, exit codes, timing, and working directory.
- Tags human and agent activity.
- Records git context for commands and commits.
- Keeps the data local by default.
- Surfaces the evidence in a dashboard, search, analytics, and daily summaries.

## Collector Quick Start

Install the shell hooks:

```bash
cargo run --manifest-path crates/collector/Cargo.toml -- install-hooks
cargo run --manifest-path crates/collector/Cargo.toml -- install-hooks --dry-run
```

Remove the shell hooks:

```bash
cargo run --manifest-path crates/collector/Cargo.toml -- uninstall-hooks
cargo run --manifest-path crates/collector/Cargo.toml -- uninstall-hooks --dry-run
```

Useful collector commands:

```bash
cargo run --manifest-path crates/collector/Cargo.toml -- session-id
cargo run --manifest-path crates/collector/Cargo.toml -- hook bash
```

## Development

Run the collector tests:

```bash
cargo test --manifest-path crates/collector/Cargo.toml
```

Type-check the dashboard:

```bash
cd apps/web
npm run typecheck
```
