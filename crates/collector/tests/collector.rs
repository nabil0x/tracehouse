use std::fs;
use std::path::PathBuf;
use std::process::Command;

use chrono::Utc;
use serde_json::Map;
use tempfile::tempdir;
use tracehouse_collector::collector::{
    build_event, create_finish_options, create_start_options, finish_capture, start_capture,
};
use tracehouse_collector::config::CollectorConfig;
use tracehouse_collector::detect::detect_actor;
use tracehouse_collector::event::{ActorType, PendingCapture};
use tracehouse_collector::git::collect_git_context;
use tracehouse_collector::hook::{render_hook, ShellKind};
use uuid::Uuid;

#[test]
fn start_and_finish_round_trip_builds_event() {
    let tempdir = tempdir().expect("tempdir");
    let config = CollectorConfig::for_tests(tempdir.path().to_path_buf());
    let start = create_start_options(
        "bash".to_string(),
        "session-1".to_string(),
        tempdir.path().to_path_buf(),
        None,
        None,
        None,
        None,
        Map::new(),
    );
    let capture_id = start_capture(&config, start)
        .expect("start capture")
        .expect("capture id");
    let finish = create_finish_options(
        capture_id.clone(),
        "session-1".to_string(),
        "bash".to_string(),
        tempdir.path().to_path_buf(),
        Some("echo hello".to_string()),
        0,
        true,
    );
    let event = finish_capture(&config, finish)
        .expect("finish capture")
        .expect("event");
    assert_eq!(event.command, "echo hello");
    assert_eq!(event.shell, "bash");
    assert_eq!(event.host, "test-host");
    assert_eq!(event.exit_code, 0);
}

#[test]
fn hook_templates_contain_shell_specific_entrypoints() {
    let bash = render_hook(ShellKind::Bash);
    assert!(bash.contains("Tracehouse bash hook"));
    assert!(bash.contains("TRACEHOUSE_COLLECTOR_BIN"));
    assert!(bash.contains("tracehouse-collector"));
    assert!(!bash.contains("ABSOLUTELY_COLLECTOR_BIN"));
    assert!(bash.contains("PROMPT_COMMAND"));
    assert!(bash.contains("DEBUG"));
    assert!(bash.contains("ABSOLUTELY_TRANSCRIPT_FILE"));
    assert!(bash.contains("agent-run"));

    let zsh = render_hook(ShellKind::Zsh);
    assert!(zsh.contains("Tracehouse zsh hook"));
    assert!(zsh.contains("TRACEHOUSE_COLLECTOR_BIN"));
    assert!(zsh.contains("preexec"));
    assert!(zsh.contains("precmd"));
    assert!(zsh.contains("ABSOLUTELY_TRANSCRIPT_FILE"));
    assert!(zsh.contains("agent-run"));

    let fish = render_hook(ShellKind::Fish);
    assert!(fish.contains("Tracehouse fish hook"));
    assert!(fish.contains("TRACEHOUSE_COLLECTOR_BIN"));
    assert!(fish.contains("tracehouse-collector"));
    assert!(!fish.contains("ABSOLUTELY_COLLECTOR_BIN"));
    assert!(fish.contains("fish_preexec"));
    assert!(fish.contains("fish_postexec"));
    assert!(fish.contains("ABSOLUTELY_TRANSCRIPT_FILE"));
    assert!(fish.contains("agent-run"));

    let powershell = render_hook(ShellKind::Powershell);
    assert!(powershell.contains("Tracehouse PowerShell hook"));
    assert!(powershell.contains("TRACEHOUSE_COLLECTOR_BIN"));
    assert!(!powershell.contains("ABSOLUTELY_COLLECTOR_BIN"));
    assert!(powershell.contains("AddToHistoryHandler"));
    assert!(powershell.contains("function prompt"));
    assert!(powershell.contains("Start-Transcript"));
    assert!(powershell.contains("ABSOLUTELY_TRANSCRIPT_FILE"));
}

#[test]
fn detect_actor_from_known_agent_command() {
    let env = std::collections::HashMap::new();
    let actor = detect_actor("codex run", &env, "session-2", None);
    assert_eq!(actor.actor_type, ActorType::Agent);
    assert_eq!(actor.actor_name.as_deref(), Some("Codex CLI"));
    assert!(actor.agent_session_id.contains("session-2"));
}

#[test]
fn build_event_includes_git_metadata_when_present() {
    let pending = PendingCapture {
        capture_id: Uuid::new_v4().to_string(),
        shell: "bash".to_string(),
        host: "test-host".to_string(),
        session_id: "session-3".to_string(),
        cwd: "/tmp/project".to_string(),
        timestamp_start: Utc::now(),
        command: Some("git commit -m \"done\"".to_string()),
        actor_type: ActorType::Human,
        actor_name: None,
        agent_session_id: String::new(),
        metadata: Map::new(),
    };

    let actor = tracehouse_collector::detect::ActorContext::human();
    let git_context = tracehouse_collector::event::GitContext {
        repository_name: Some("project".to_string()),
        repository_root: Some("/tmp/project".to_string()),
        branch: Some("main".to_string()),
        commit_hash: Some("abc123".to_string()),
        changed_files: vec![],
        commit_message: Some("done".to_string()),
        commit_snapshot: None,
    };
    let event = build_event(
        pending,
        "git commit -m \"done\"".to_string(),
        PathBuf::from("/tmp/project"),
        "bash".to_string(),
        0,
        Utc::now(),
        42,
        actor,
        Some(git_context),
        None,
        None,
    );
    assert_eq!(event.repository_name.as_deref(), Some("project"));
    assert_eq!(event.git_commit_hash.as_deref(), Some("abc123"));
    assert_eq!(
        event
            .metadata
            .get("git_commit_message")
            .and_then(|value| value.as_str()),
        Some("done")
    );
}

#[test]
fn collect_git_context_captures_commit_snapshot() {
    let tempdir = tempdir().expect("tempdir");
    let repo = tempdir.path();

    run_git(repo, &["init"]);
    run_git(repo, &["config", "user.email", "test@example.com"]);
    run_git(repo, &["config", "user.name", "Test User"]);
    fs::write(repo.join("README.md"), "hello world\n").expect("write file");
    run_git(repo, &["add", "README.md"]);
    run_git(repo, &["commit", "-m", "Initial commit"]);

    let context =
        collect_git_context(repo, "git commit -m \"Initial commit\"", 0).expect("git context");
    let snapshot = context.commit_snapshot.expect("commit snapshot");

    let head = git_output(repo, &["rev-parse", "HEAD"]);
    assert_eq!(snapshot.commit_hash, head);
    assert_eq!(snapshot.message, "Initial commit");
    assert!(!snapshot.file_changes.is_empty());
    assert!(snapshot
        .file_changes
        .iter()
        .any(|change| change.path == "README.md"));
    assert!(snapshot
        .diff_summary
        .as_deref()
        .unwrap_or("")
        .contains("README.md"));
}

fn run_git(repo: &std::path::Path, args: &[&str]) {
    let status = Command::new("git")
        .args(args)
        .current_dir(repo)
        .status()
        .expect("git command");
    assert!(status.success(), "git {:?} failed with {status}", args);
}

fn git_output(repo: &std::path::Path, args: &[&str]) -> String {
    let output = Command::new("git")
        .args(args)
        .current_dir(repo)
        .output()
        .expect("git output");
    assert!(output.status.success(), "git {:?} failed", args);
    String::from_utf8(output.stdout)
        .expect("utf8")
        .trim()
        .to_string()
}
