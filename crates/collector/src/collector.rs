use std::collections::HashMap;
use std::env;
use std::fs;
use std::path::{Path, PathBuf};
use std::time::Duration;

use anyhow::{Context, Result};
use chrono::{DateTime, Utc};
use reqwest::blocking::Client;
use serde_json::{json, Map, Value};

use crate::config::CollectorConfig;
use crate::detect::{detect_actor, ActorContext};
use crate::event::{ActorType, CommandEvent, GitContext, PendingCapture};
use crate::git::collect_git_context;
use crate::state::{
    capture_id, delete_pending_capture, read_pending_capture, write_pending_capture,
};

#[derive(Debug, Clone)]
pub struct StartOptions {
    pub shell: String,
    pub session_id: String,
    pub cwd: PathBuf,
    pub command: Option<String>,
    pub actor_type: Option<ActorType>,
    pub actor_name: Option<String>,
    pub agent_session_id: Option<String>,
    pub metadata: Map<String, Value>,
}

#[derive(Debug, Clone)]
pub struct FinishOptions {
    pub capture_id: String,
    pub session_id: String,
    pub shell: String,
    pub cwd: PathBuf,
    pub command: Option<String>,
    pub exit_code: i32,
    pub dry_run: bool,
}

pub fn start_capture(config: &CollectorConfig, opts: StartOptions) -> Result<Option<String>> {
    if config.paused || config.is_dir_excluded(&opts.cwd) {
        return Ok(None);
    }
    if let Some(command) = opts.command.as_deref() {
        if config.is_command_excluded(command) {
            return Ok(None);
        }
    }

    let capture_id = capture_id();
    let pending = PendingCapture {
        capture_id: capture_id.clone(),
        shell: opts.shell,
        host: config.host.clone(),
        session_id: opts.session_id,
        cwd: canonicalize_path(&opts.cwd).display().to_string(),
        timestamp_start: Utc::now(),
        command: opts.command,
        actor_type: opts.actor_type.unwrap_or(ActorType::Human),
        actor_name: opts.actor_name,
        agent_session_id: opts.agent_session_id.unwrap_or_default(),
        metadata: opts.metadata,
    };
    write_pending_capture(&config.state_dir, &pending)?;
    Ok(Some(capture_id))
}

pub fn finish_capture(
    config: &CollectorConfig,
    opts: FinishOptions,
) -> Result<Option<CommandEvent>> {
    let Some(pending) =
        read_pending_capture(&config.state_dir, &opts.session_id, &opts.capture_id)?
    else {
        return Ok(None);
    };

    let command = opts
        .command
        .or_else(|| pending.command.clone())
        .unwrap_or_default()
        .trim()
        .to_string();
    let cwd = canonicalize_path(&opts.cwd);
    if command.is_empty()
        || config.paused
        || config.is_dir_excluded(&cwd)
        || config.is_command_excluded(&command)
    {
        delete_pending_capture(&config.state_dir, &opts.session_id, &opts.capture_id)?;
        if let Some(path) = transcript_file_path() {
            let _ = fs::remove_file(path);
        }
        return Ok(None);
    }

    let environment = current_environment();
    let actor = detect_actor(
        &command,
        &environment,
        &pending.session_id,
        pending_actor_context(&pending),
    );
    let timestamp_end = Utc::now();
    let duration_ms = (timestamp_end - pending.timestamp_start)
        .num_milliseconds()
        .max(0);
    let git_context = collect_git_context(&cwd, &command, opts.exit_code);
    let shell = if pending.shell.trim().is_empty() {
        opts.shell
    } else {
        pending.shell.clone()
    };
    let stdout = transcript_text();
    let event = build_event(
        pending,
        command,
        cwd,
        shell,
        opts.exit_code,
        timestamp_end,
        duration_ms,
        actor,
        git_context,
        stdout,
        None,
    );

    if !opts.dry_run {
        if let Err(error) = post_event(&config.api_url, &event) {
            eprintln!("tracehouse-collector: failed to post event: {error:#}");
        } else {
            delete_pending_capture(&config.state_dir, &opts.session_id, &opts.capture_id)?;
            if let Some(path) = transcript_file_path() {
                let _ = fs::remove_file(path);
            }
        }
    } else {
        delete_pending_capture(&config.state_dir, &opts.session_id, &opts.capture_id)?;
        if let Some(path) = transcript_file_path() {
            let _ = fs::remove_file(path);
        }
    }

    Ok(Some(event))
}

pub fn post_event(api_url: &str, event: &CommandEvent) -> Result<()> {
    let client = Client::builder()
        .timeout(Duration::from_secs(3))
        .build()
        .context("building HTTP client")?;
    let endpoint = format!("{}/commands", api_url.trim_end_matches('/'));
    let response = client
        .post(endpoint)
        .json(event)
        .send()
        .context("sending ingest request")?;
    if !response.status().is_success() {
        anyhow::bail!("ingest endpoint returned {}", response.status());
    }
    Ok(())
}

pub fn build_event(
    pending: PendingCapture,
    command: String,
    cwd: PathBuf,
    shell: String,
    exit_code: i32,
    timestamp_end: DateTime<Utc>,
    duration_ms: i64,
    actor: ActorContext,
    git_context: Option<GitContext>,
    stdout: Option<String>,
    stderr: Option<String>,
) -> CommandEvent {
    let PendingCapture {
        capture_id: _,
        shell: _,
        host,
        session_id,
        cwd: _,
        timestamp_start,
        command: _,
        actor_type: _,
        actor_name: _,
        agent_session_id: _,
        metadata: mut event_metadata,
    } = pending;
    let command = command.trim().to_string();
    if let Some(git) = git_context.as_ref() {
        event_metadata.insert("git_changed_files".to_string(), json!(git.changed_files));
        event_metadata.insert(
            "git_status_count".to_string(),
            json!(git.changed_files.len()),
        );
        if let Some(message) = git.commit_message.clone() {
            event_metadata.insert("git_commit_message".to_string(), json!(message));
        }
        if let Some(snapshot) = git.commit_snapshot.as_ref() {
            event_metadata.insert("git_commit_snapshot".to_string(), json!(snapshot));
        }
    }

    CommandEvent {
        command,
        cwd: cwd.display().to_string(),
        timestamp_start,
        timestamp_end,
        duration_ms,
        exit_code,
        shell,
        host,
        session_id,
        stdout,
        stderr,
        actor_type: actor.actor_type,
        actor_name: actor.actor_name,
        agent_session_id: actor.agent_session_id,
        repository_name: git_context
            .as_ref()
            .and_then(|git| git.repository_name.clone()),
        repository_root: git_context
            .as_ref()
            .and_then(|git| git.repository_root.clone()),
        git_branch: git_context.as_ref().and_then(|git| git.branch.clone()),
        git_commit_hash: git_context.as_ref().and_then(|git| git.commit_hash.clone()),
        metadata: event_metadata,
    }
}

pub fn create_start_options(
    shell: String,
    session_id: String,
    cwd: PathBuf,
    command: Option<String>,
    actor_type: Option<ActorType>,
    actor_name: Option<String>,
    agent_session_id: Option<String>,
    metadata: Map<String, Value>,
) -> StartOptions {
    StartOptions {
        shell,
        session_id,
        cwd,
        command,
        actor_type,
        actor_name,
        agent_session_id,
        metadata,
    }
}

pub fn create_finish_options(
    capture_id: String,
    session_id: String,
    shell: String,
    cwd: PathBuf,
    command: Option<String>,
    exit_code: i32,
    dry_run: bool,
) -> FinishOptions {
    FinishOptions {
        capture_id,
        session_id,
        shell,
        cwd,
        command,
        exit_code,
        dry_run,
    }
}

fn current_environment() -> HashMap<String, String> {
    std::env::vars().collect()
}

fn pending_actor_context(pending: &PendingCapture) -> Option<ActorContext> {
    if pending.actor_type == ActorType::Agent || pending.actor_name.is_some() {
        Some(ActorContext {
            actor_type: pending.actor_type,
            actor_name: pending.actor_name.clone(),
            agent_session_id: pending.agent_session_id.clone(),
        })
    } else {
        None
    }
}

fn canonicalize_path(path: &Path) -> PathBuf {
    path.canonicalize().unwrap_or_else(|_| path.to_path_buf())
}

fn transcript_file_path() -> Option<PathBuf> {
    env::var_os("ABSOLUTELY_TRANSCRIPT_FILE")
        .filter(|value| !value.is_empty())
        .map(PathBuf::from)
}

fn transcript_text() -> Option<String> {
    let path = transcript_file_path()?;
    let bytes = fs::read(&path).ok()?;
    if bytes.is_empty() {
        return None;
    }
    Some(String::from_utf8_lossy(&bytes).into_owned())
}
