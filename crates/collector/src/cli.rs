use std::path::PathBuf;

use anyhow::Result;
use clap::{Parser, Subcommand};
use serde_json::Map;

use crate::collector::{
    create_finish_options, create_start_options, finish_capture, start_capture,
};
use crate::config::CollectorConfig;
use crate::event::ActorType;
use crate::hook::{render_hook, shell_name, ShellKind};
use crate::install::{install_all_hooks, uninstall_all_hooks};
use crate::state::capture_id;
use crate::transcript::run_agent_transcript;

#[derive(Debug, Parser)]
#[command(author, version, about = "Capture terminal activity for Tracehouse")]
struct Cli {
    #[command(subcommand)]
    command: Commands,
}

#[derive(Debug, Subcommand)]
enum Commands {
    SessionId,
    Start {
        #[arg(long)]
        shell: String,
        #[arg(long)]
        session_id: String,
        #[arg(long)]
        cwd: PathBuf,
        #[arg(long)]
        command: Option<String>,
        #[arg(long)]
        actor_type: Option<ActorType>,
        #[arg(long)]
        actor_name: Option<String>,
        #[arg(long)]
        agent_session_id: Option<String>,
    },
    Finish {
        #[arg(long)]
        capture_id: String,
        #[arg(long)]
        session_id: String,
        #[arg(long)]
        shell: String,
        #[arg(long)]
        cwd: PathBuf,
        #[arg(long)]
        command: Option<String>,
        #[arg(long)]
        exit_code: i32,
        #[arg(long, default_value_t = false)]
        dry_run: bool,
    },
    Hook {
        #[arg(value_enum)]
        shell: ShellKind,
    },
    InstallHooks {
        #[arg(long, default_value_t = false)]
        dry_run: bool,
    },
    UninstallHooks {
        #[arg(long, default_value_t = false)]
        dry_run: bool,
    },
    AgentRun {
        #[arg(last = true)]
        command: Vec<String>,
    },
    CaptureId,
}

pub fn run() -> Result<()> {
    let cli = Cli::parse();
    let config = CollectorConfig::from_env();

    match cli.command {
        Commands::SessionId => {
            println!("{}", capture_id());
        }
        Commands::CaptureId => {
            println!("{}", capture_id());
        }
        Commands::Start {
            shell,
            session_id,
            cwd,
            command,
            actor_type,
            actor_name,
            agent_session_id,
        } => {
            let start = create_start_options(
                shell,
                session_id,
                cwd,
                command,
                actor_type,
                actor_name,
                agent_session_id,
                Map::new(),
            );
            if let Some(id) = start_capture(&config, start)? {
                println!("{id}");
            }
        }
        Commands::Finish {
            capture_id,
            session_id,
            shell,
            cwd,
            command,
            exit_code,
            dry_run,
        } => {
            let finish = create_finish_options(
                capture_id, session_id, shell, cwd, command, exit_code, dry_run,
            );
            if let Some(event) = finish_capture(&config, finish)? {
                if dry_run {
                    println!("{}", serde_json::to_string_pretty(&event)?);
                }
            }
        }
        Commands::Hook { shell } => {
            print!("{}", render_hook(shell));
        }
        Commands::InstallHooks { dry_run } => {
            let reports = install_all_hooks(dry_run)?;
            for report in reports {
                let status = if report.changed {
                    if dry_run {
                        "would update"
                    } else if report.created {
                        "created"
                    } else {
                        "updated"
                    }
                } else if dry_run {
                    "would keep"
                } else {
                    "unchanged"
                };
                println!(
                    "{}: {} {}",
                    shell_name(report.shell),
                    status,
                    report.path.display()
                );
            }
        }
        Commands::UninstallHooks { dry_run } => {
            let reports = uninstall_all_hooks(dry_run)?;
            for report in reports {
                let status = if report.changed {
                    if dry_run {
                        "would remove"
                    } else {
                        "removed"
                    }
                } else if dry_run {
                    "would keep"
                } else {
                    "unchanged"
                };
                println!(
                    "{}: {} {}",
                    shell_name(report.shell),
                    status,
                    report.path.display()
                );
            }
        }
        Commands::AgentRun { command } => {
            let code = run_agent_transcript(&command)?;
            std::process::exit(code);
        }
    }

    Ok(())
}
