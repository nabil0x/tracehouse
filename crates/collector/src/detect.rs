use std::collections::HashMap;

use crate::event::ActorType;

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ActorContext {
    pub actor_type: ActorType,
    pub actor_name: Option<String>,
    pub agent_session_id: String,
}

impl ActorContext {
    pub fn human() -> Self {
        Self {
            actor_type: ActorType::Human,
            actor_name: None,
            agent_session_id: String::new(),
        }
    }
}

pub fn detect_actor(
    command: &str,
    env: &HashMap<String, String>,
    session_id: &str,
    existing_actor: Option<ActorContext>,
) -> ActorContext {
    if let Some(actor) = existing_actor {
        return actor;
    }

    if let Some(actor_name) = env_agent_name(env) {
        return agent_actor(actor_name, session_id);
    }

    let command_lower = command.to_lowercase();
    let first_token = command_lower.split_whitespace().next().unwrap_or("");

    if let Some(actor_name) = command_agent_name(first_token, &command_lower) {
        return agent_actor(actor_name, session_id);
    }

    ActorContext::human()
}

fn env_agent_name(env: &HashMap<String, String>) -> Option<String> {
    let candidates = [
        ("ABSOLUTELY_AGENT_NAME", "custom agent"),
        ("ABSOLUTELY_FORCE_AGENT_NAME", "custom agent"),
        ("ABSOLUTELY_ACTOR_NAME", "custom agent"),
        ("CLAUDE_CODE_AGENT_NAME", "Claude Code"),
        ("CLAUDECODE_AGENT_NAME", "Claude Code"),
        ("CURSOR_AGENT_NAME", "Cursor Agent"),
        ("AIDER_AGENT_NAME", "Aider"),
        ("GEMINI_CLI_AGENT_NAME", "Gemini CLI"),
        ("CODEX_CLI_AGENT_NAME", "Codex CLI"),
    ];

    for (key, default_name) in candidates {
        if let Some(value) = env.get(key).filter(|value| !value.trim().is_empty()) {
            return Some(value.to_string());
        }
        if env.contains_key(key) {
            return Some(default_name.to_string());
        }
    }

    if env.contains_key("CLAUDECODE") || env.contains_key("CLAUDE_CODE") {
        return Some("Claude Code".to_string());
    }
    if env.contains_key("CURSOR_TRACE_ID") || env.contains_key("CURSOR_AGENT") {
        return Some("Cursor Agent".to_string());
    }
    if env.contains_key("AIDER") || env.contains_key("AIDER_SESSION_ID") {
        return Some("Aider".to_string());
    }
    if env.contains_key("GEMINI_CLI") || env.contains_key("GEMINI_SESSION_ID") {
        return Some("Gemini CLI".to_string());
    }
    if env.contains_key("CODEX_CLI") || env.contains_key("CODEX_SESSION_ID") {
        return Some("Codex CLI".to_string());
    }

    None
}

fn command_agent_name(first_token: &str, command_lower: &str) -> Option<String> {
    let known = [
        ("claude", "Claude Code"),
        ("claude-code", "Claude Code"),
        ("cursor", "Cursor Agent"),
        ("cursor-agent", "Cursor Agent"),
        ("aider", "Aider"),
        ("gemini", "Gemini CLI"),
        ("gemini-cli", "Gemini CLI"),
        ("codex", "Codex CLI"),
        ("codex-cli", "Codex CLI"),
    ];

    for (needle, name) in known {
        if first_token == needle || command_lower.contains(needle) {
            return Some(name.to_string());
        }
    }

    None
}

fn agent_actor(actor_name: String, session_id: &str) -> ActorContext {
    let agent_session_id = format!("{session_id}:{actor_name}");
    ActorContext {
        actor_type: ActorType::Agent,
        actor_name: Some(actor_name),
        agent_session_id,
    }
}
