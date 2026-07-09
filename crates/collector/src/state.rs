use std::fs;
use std::path::{Path, PathBuf};

use anyhow::{Context, Result};
use uuid::Uuid;

use crate::event::PendingCapture;

pub fn capture_id() -> String {
    Uuid::new_v4().to_string()
}

pub fn sanitize_component(value: &str) -> String {
    let mut out = String::with_capacity(value.len());
    for ch in value.chars() {
        if ch.is_ascii_alphanumeric() || matches!(ch, '-' | '_' | '.') {
            out.push(ch);
        } else {
            out.push('_');
        }
    }
    if out.is_empty() {
        "default".to_string()
    } else {
        out
    }
}

pub fn pending_capture_path(base: &Path, session_id: &str, capture_id: &str) -> PathBuf {
    base.join("pending")
        .join(sanitize_component(session_id))
        .join(format!("{capture_id}.json"))
}

pub fn write_pending_capture(base: &Path, capture: &PendingCapture) -> Result<()> {
    let path = pending_capture_path(base, &capture.session_id, &capture.capture_id);
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent).with_context(|| format!("creating pending dir {parent:?}"))?;
    }
    let json = serde_json::to_vec_pretty(capture)?;
    fs::write(&path, json).with_context(|| format!("writing pending capture {path:?}"))?;
    Ok(())
}

pub fn read_pending_capture(
    base: &Path,
    session_id: &str,
    capture_id: &str,
) -> Result<Option<PendingCapture>> {
    let path = pending_capture_path(base, session_id, capture_id);
    if !path.exists() {
        return Ok(None);
    }
    let bytes = fs::read(&path).with_context(|| format!("reading pending capture {path:?}"))?;
    let capture = serde_json::from_slice(&bytes)
        .with_context(|| format!("parsing pending capture {path:?}"))?;
    Ok(Some(capture))
}

pub fn delete_pending_capture(base: &Path, session_id: &str, capture_id: &str) -> Result<()> {
    let path = pending_capture_path(base, session_id, capture_id);
    if path.exists() {
        fs::remove_file(&path).with_context(|| format!("removing pending capture {path:?}"))?;
    }
    Ok(())
}
