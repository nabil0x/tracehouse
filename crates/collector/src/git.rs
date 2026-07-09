use std::path::Path;
use std::process::Command;

use chrono::{DateTime, TimeZone, Utc};

use crate::event::{GitCommitFileChange, GitCommitSnapshot, GitContext, GitFileChange};

pub fn collect_git_context(cwd: &Path, command: &str, exit_code: i32) -> Option<GitContext> {
    let repository_root = git_output(cwd, &["rev-parse", "--show-toplevel"])?;
    let root_path = Path::new(&repository_root);
    let repository_name = root_path
        .file_name()
        .and_then(|value| value.to_str())
        .map(|value| value.to_string())
        .unwrap_or_else(|| repository_root.clone());
    let branch = git_output(cwd, &["rev-parse", "--abbrev-ref", "HEAD"]);
    let commit_hash = git_output(cwd, &["rev-parse", "HEAD"]);
    let changed_files = git_status_lines(cwd);
    let commit_snapshot = if looks_like_git_commit(command) && exit_code == 0 {
        collect_commit_snapshot(cwd)
    } else {
        None
    };
    let commit_message = commit_snapshot
        .as_ref()
        .map(|snapshot| snapshot.message.clone());

    Some(GitContext {
        repository_name: Some(repository_name),
        repository_root: Some(repository_root),
        branch,
        commit_hash,
        changed_files,
        commit_message,
        commit_snapshot,
    })
}

fn looks_like_git_commit(command: &str) -> bool {
    let normalized = command.trim().to_lowercase();
    normalized.starts_with("git commit ")
        || normalized == "git commit"
        || normalized.contains(" git commit ")
}

fn collect_commit_snapshot(cwd: &Path) -> Option<GitCommitSnapshot> {
    let header = git_output(
        cwd,
        &[
            "show",
            "-s",
            "--format=%H%x1f%an%x1f%at%x1f%ct%x1f%B",
            "HEAD",
        ],
    )?;
    let mut parts = header.splitn(5, '\u{1f}');
    let commit_hash = parts.next()?.trim().to_string();
    let author_name = parts
        .next()
        .map(|value| value.trim().to_string())
        .filter(|value| !value.is_empty());
    let authored_at = parts.next().and_then(parse_git_timestamp);
    let committed_at = parts.next().and_then(parse_git_timestamp);
    let message = parts
        .next()
        .map(|value| value.trim().to_string())
        .filter(|value| !value.is_empty())?;
    let diff_summary = git_output(
        cwd,
        &["show", "--stat", "--format=", "--find-renames", "HEAD"],
    )
    .map(|value| value.trim().to_string())
    .filter(|value| !value.is_empty());
    let file_changes = collect_commit_file_changes(cwd);

    Some(GitCommitSnapshot {
        commit_hash,
        message,
        author_name,
        authored_at,
        committed_at,
        diff_summary,
        file_changes,
    })
}

fn git_status_lines(cwd: &Path) -> Vec<GitFileChange> {
    let Some(output) = git_output(cwd, &["status", "--porcelain=v1"]) else {
        return Vec::new();
    };

    output
        .lines()
        .filter_map(|line| {
            let trimmed = line.trim();
            if trimmed.len() < 3 {
                return None;
            }
            let status = trimmed.get(0..2)?.trim().to_string();
            let raw_path = trimmed.get(3..)?.trim();
            let path = raw_path
                .rsplit_once(" -> ")
                .map(|(_, new_path)| new_path.trim().to_string())
                .unwrap_or_else(|| raw_path.to_string());
            Some(GitFileChange {
                status,
                path,
                raw: trimmed.to_string(),
            })
        })
        .collect()
}

fn collect_commit_file_changes(cwd: &Path) -> Vec<GitCommitFileChange> {
    let status_output = git_output(
        cwd,
        &[
            "diff-tree",
            "--root",
            "--no-commit-id",
            "--name-status",
            "-r",
            "-M",
            "HEAD",
        ],
    )
    .unwrap_or_default();
    let numstat_output = git_output(
        cwd,
        &[
            "diff-tree",
            "--root",
            "--no-commit-id",
            "--numstat",
            "-r",
            "-M",
            "HEAD",
        ],
    )
    .unwrap_or_default();
    let status_lines: Vec<ParsedCommitStatusLine> = status_output
        .lines()
        .filter_map(parse_commit_status_line)
        .collect();
    let numstat_lines: Vec<ParsedCommitNumstatLine> = numstat_output
        .lines()
        .filter_map(parse_commit_numstat_line)
        .collect();
    let total = status_lines.len().max(numstat_lines.len());
    let mut file_changes = Vec::with_capacity(total);

    for index in 0..total {
        let Some(status_line) = status_lines.get(index) else {
            continue;
        };
        let numstat_line = numstat_lines.get(index);
        file_changes.push(GitCommitFileChange {
            path: status_line.path.clone(),
            old_path: status_line.old_path.clone(),
            change_type: change_type_from_status(&status_line.status),
            lines_added: numstat_line.map(|line| line.lines_added).unwrap_or(0),
            lines_removed: numstat_line.map(|line| line.lines_removed).unwrap_or(0),
            status: status_line.status.clone(),
            raw: status_line.raw.clone(),
        });
    }

    file_changes
}

fn parse_commit_status_line(line: &str) -> Option<ParsedCommitStatusLine> {
    let trimmed = line.trim();
    if trimmed.is_empty() {
        return None;
    }
    let mut parts = trimmed.split('\t');
    let status = parts.next()?.trim().to_string();
    let first_path = parts.next()?.trim().to_string();
    let second_path = parts.next().map(|value| value.trim().to_string());
    let (path, old_path) = match second_path {
        Some(new_path) if !new_path.is_empty() => (new_path, Some(first_path)),
        _ => (first_path, None),
    };

    Some(ParsedCommitStatusLine {
        status,
        path,
        old_path,
        raw: trimmed.to_string(),
    })
}

fn parse_commit_numstat_line(line: &str) -> Option<ParsedCommitNumstatLine> {
    let trimmed = line.trim();
    if trimmed.is_empty() {
        return None;
    }
    let mut parts = trimmed.split('\t');
    let lines_added = parse_numstat_count(parts.next()?)?;
    let lines_removed = parse_numstat_count(parts.next()?)?;

    Some(ParsedCommitNumstatLine {
        lines_added,
        lines_removed,
    })
}

fn parse_numstat_count(value: &str) -> Option<i64> {
    if value.trim() == "-" {
        return Some(0);
    }
    value.trim().parse().ok()
}

fn parse_git_timestamp(value: &str) -> Option<DateTime<Utc>> {
    let seconds: i64 = value.trim().parse().ok()?;
    Utc.timestamp_opt(seconds, 0).single()
}

fn change_type_from_status(status: &str) -> String {
    match status.chars().next().unwrap_or('M') {
        'A' => "added".to_string(),
        'D' => "deleted".to_string(),
        'R' | 'C' => "renamed".to_string(),
        _ => "modified".to_string(),
    }
}

fn git_output(cwd: &Path, args: &[&str]) -> Option<String> {
    let output = Command::new("git")
        .args(args)
        .current_dir(cwd)
        .output()
        .ok()?;
    if !output.status.success() {
        return None;
    }
    String::from_utf8(output.stdout)
        .ok()
        .map(|value| value.trim().to_string())
        .filter(|value| !value.is_empty())
}

#[derive(Debug)]
struct ParsedCommitStatusLine {
    status: String,
    path: String,
    old_path: Option<String>,
    raw: String,
}

#[derive(Debug)]
struct ParsedCommitNumstatLine {
    lines_added: i64,
    lines_removed: i64,
}
