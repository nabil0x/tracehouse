use std::env;
use std::path::{Path, PathBuf};

#[derive(Debug, Clone)]
pub struct CollectorConfig {
    pub api_url: String,
    pub host: String,
    pub state_dir: PathBuf,
    pub paused: bool,
    pub exclude_dirs: Vec<PathBuf>,
    pub exclude_commands: Vec<String>,
    pub collector_bin: String,
}

impl CollectorConfig {
    pub fn from_env() -> Self {
        let host = env::var("ABSOLUTELY_HOST")
            .ok()
            .filter(|value| !value.trim().is_empty())
            .unwrap_or_else(local_hostname);
        let api_url = env::var("ABSOLUTELY_API_URL")
            .ok()
            .filter(|value| !value.trim().is_empty())
            .unwrap_or_else(|| "http://127.0.0.1:18400".to_string());
        let state_dir = env::var("ABSOLUTELY_STATE_DIR")
            .ok()
            .filter(|value| !value.trim().is_empty())
            .map(PathBuf::from)
            .unwrap_or_else(default_state_dir);
        let paused = env::var("ABSOLUTELY_PAUSED")
            .map(|value| is_truthy(&value))
            .unwrap_or(false);
        let exclude_dirs = parse_path_list("ABSOLUTELY_EXCLUDE_DIRS");
        let exclude_commands = parse_string_list("ABSOLUTELY_EXCLUDE_COMMANDS");
        let collector_bin = env::var("TRACEHOUSE_COLLECTOR_BIN")
            .ok()
            .filter(|value| !value.trim().is_empty())
            .unwrap_or_else(|| "tracehouse-collector".to_string());

        Self {
            api_url,
            host,
            state_dir,
            paused,
            exclude_dirs,
            exclude_commands,
            collector_bin,
        }
    }

    pub fn for_tests(state_dir: PathBuf) -> Self {
        Self {
            api_url: "http://127.0.0.1:18400".to_string(),
            host: "test-host".to_string(),
            state_dir,
            paused: false,
            exclude_dirs: Vec::new(),
            exclude_commands: Vec::new(),
            collector_bin: "tracehouse-collector".to_string(),
        }
    }

    pub fn pending_dir(&self) -> PathBuf {
        self.state_dir.join("pending")
    }

    pub fn is_dir_excluded(&self, cwd: &Path) -> bool {
        let resolved = cwd.canonicalize().unwrap_or_else(|_| cwd.to_path_buf());
        self.exclude_dirs.iter().any(|exclude| {
            let candidate = exclude.canonicalize().unwrap_or_else(|_| exclude.clone());
            resolved.starts_with(&candidate) || resolved == candidate
        })
    }

    pub fn is_command_excluded(&self, command: &str) -> bool {
        let normalized = command.to_lowercase();
        self.exclude_commands
            .iter()
            .any(|pattern| normalized.contains(&pattern.to_lowercase()))
    }
}

fn local_hostname() -> String {
    hostname::get()
        .ok()
        .and_then(|value| value.into_string().ok())
        .filter(|value| !value.trim().is_empty())
        .unwrap_or_else(|| "unknown-host".to_string())
}

fn default_state_dir() -> PathBuf {
    if let Ok(dir) = env::var("XDG_STATE_HOME") {
        return PathBuf::from(dir).join("absolutely");
    }
    if let Some(home) = env::var_os("HOME") {
        return PathBuf::from(home).join(".local/state/absolutely");
    }
    PathBuf::from(".absolutely")
}

fn parse_string_list(key: &str) -> Vec<String> {
    env::var(key)
        .ok()
        .map(|value| {
            value
                .split([',', ':'])
                .map(str::trim)
                .filter(|entry| !entry.is_empty())
                .map(ToOwned::to_owned)
                .collect()
        })
        .unwrap_or_default()
}

fn parse_path_list(key: &str) -> Vec<PathBuf> {
    env::var(key)
        .ok()
        .map(|value| {
            value
                .split([',', ':'])
                .map(str::trim)
                .filter(|entry| !entry.is_empty())
                .map(PathBuf::from)
                .collect()
        })
        .unwrap_or_default()
}

fn is_truthy(value: &str) -> bool {
    matches!(
        value.trim().to_ascii_lowercase().as_str(),
        "1" | "true" | "yes" | "on"
    )
}
