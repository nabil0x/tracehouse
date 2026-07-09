use chrono::{DateTime, Utc};
use clap::ValueEnum;
use serde::{Deserialize, Serialize};
use serde_json::{Map, Value};

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize, ValueEnum)]
#[serde(rename_all = "lowercase")]
pub enum ActorType {
    Human,
    Agent,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub struct CommandEvent {
    pub command: String,
    pub cwd: String,
    pub timestamp_start: DateTime<Utc>,
    pub timestamp_end: DateTime<Utc>,
    pub duration_ms: i64,
    pub exit_code: i32,
    pub shell: String,
    pub host: String,
    pub session_id: String,
    pub stdout: Option<String>,
    pub stderr: Option<String>,
    pub actor_type: ActorType,
    pub actor_name: Option<String>,
    pub agent_session_id: String,
    pub repository_name: Option<String>,
    pub repository_root: Option<String>,
    pub git_branch: Option<String>,
    pub git_commit_hash: Option<String>,
    #[serde(default)]
    pub metadata: Map<String, Value>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub struct PendingCapture {
    pub capture_id: String,
    pub shell: String,
    pub host: String,
    pub session_id: String,
    pub cwd: String,
    pub timestamp_start: DateTime<Utc>,
    pub command: Option<String>,
    pub actor_type: ActorType,
    pub actor_name: Option<String>,
    pub agent_session_id: String,
    #[serde(default)]
    pub metadata: Map<String, Value>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize, Default)]
#[serde(rename_all = "snake_case")]
pub struct GitContext {
    pub repository_name: Option<String>,
    pub repository_root: Option<String>,
    pub branch: Option<String>,
    pub commit_hash: Option<String>,
    pub changed_files: Vec<GitFileChange>,
    pub commit_message: Option<String>,
    pub commit_snapshot: Option<GitCommitSnapshot>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub struct GitFileChange {
    pub status: String,
    pub path: String,
    pub raw: String,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub struct GitCommitSnapshot {
    pub commit_hash: String,
    pub message: String,
    pub author_name: Option<String>,
    pub authored_at: Option<DateTime<Utc>>,
    pub committed_at: Option<DateTime<Utc>>,
    pub diff_summary: Option<String>,
    pub file_changes: Vec<GitCommitFileChange>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub struct GitCommitFileChange {
    pub path: String,
    pub old_path: Option<String>,
    pub change_type: String,
    pub lines_added: i64,
    pub lines_removed: i64,
    pub status: String,
    pub raw: String,
}
