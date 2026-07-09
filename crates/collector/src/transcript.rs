use std::env;
use std::fs;
use std::path::PathBuf;
use std::process::Command;

use anyhow::{Context, Result};

fn shell_escape(value: &str) -> String {
    if value.is_empty() {
        "''".to_string()
    } else {
        format!("'{}'", value.replace('\'', r#"'\''"#))
    }
}

fn build_script_command(command: &[String]) -> Result<String> {
    let (binary, args) = command
        .split_first()
        .context("agent transcript requires a command")?;
    let mut parts = Vec::with_capacity(command.len() + 1);
    parts.push("command".to_string());
    parts.push(shell_escape(binary));
    parts.extend(args.iter().map(|arg| shell_escape(arg)));
    Ok(parts.join(" "))
}

fn transcript_path() -> Option<PathBuf> {
    env::var_os("ABSOLUTELY_TRANSCRIPT_FILE")
        .filter(|value| !value.is_empty())
        .map(PathBuf::from)
}

fn run_direct(command: &[String]) -> Result<i32> {
    let (binary, args) = command
        .split_first()
        .context("agent transcript requires a command")?;
    let status = Command::new(binary)
        .args(args)
        .status()
        .with_context(|| format!("running agent command {binary}"))?;
    Ok(status.code().unwrap_or(1))
}

fn run_with_script(command: &[String], transcript_file: &PathBuf) -> Result<i32> {
    let script_command = build_script_command(command)?;
    let status = Command::new("script")
        .arg("-qefc")
        .arg(script_command)
        .arg(transcript_file)
        .status()
        .context("running transcript logger")?;
    Ok(status.code().unwrap_or(1))
}

pub fn run_agent_transcript(command: &[String]) -> Result<i32> {
    let Some(transcript_file) = transcript_path() else {
        return run_direct(command);
    };
    if let Some(parent) = transcript_file.parent() {
        fs::create_dir_all(parent)
            .with_context(|| format!("creating transcript directory {parent:?}"))?;
    }
    if transcript_file.exists() {
        let _ = fs::remove_file(&transcript_file);
    }
    match run_with_script(command, &transcript_file) {
        Ok(code) => Ok(code),
        Err(error) => {
            eprintln!("tracehouse-collector: transcript capture unavailable: {error:#}");
            run_direct(command)
        }
    }
}

#[cfg(test)]
mod tests {
    use std::env;
    use std::fs;
    use std::process::Command;

    use tempfile::tempdir;

    use super::{build_script_command, run_agent_transcript};

    #[test]
    fn build_script_command_escapes_quotes_and_spaces() {
        let command = vec![
            "codex".to_string(),
            "say hi".to_string(),
            "it's".to_string(),
            "\"quoted\"".to_string(),
        ];
        let script_command = build_script_command(&command).expect("script command");
        assert_eq!(
            script_command,
            "command 'codex' 'say hi' 'it'\\''s' '\"quoted\"'"
        );
    }

    #[test]
    fn run_agent_transcript_writes_output_file() {
        if Command::new("script").arg("--version").status().is_err() {
            return;
        }

        let tempdir = tempdir().expect("tempdir");
        let transcript_file = tempdir.path().join("transcript.log");
        let previous = env::var_os("ABSOLUTELY_TRANSCRIPT_FILE");
        env::set_var("ABSOLUTELY_TRANSCRIPT_FILE", &transcript_file);

        let status = run_agent_transcript(&[
            "python3".to_string(),
            "-c".to_string(),
            "print('hello from tracehouse')".to_string(),
        ])
        .expect("run agent transcript");

        if let Some(value) = previous {
            env::set_var("ABSOLUTELY_TRANSCRIPT_FILE", value);
        } else {
            env::remove_var("ABSOLUTELY_TRANSCRIPT_FILE");
        }

        assert_eq!(status, 0);
        let transcript = fs::read_to_string(&transcript_file).expect("transcript contents");
        assert!(transcript.contains("hello from tracehouse"));
    }
}
