use std::env;
use std::fs;
use std::path::{Path, PathBuf};

use anyhow::{Context, Result};

use crate::hook::{managed_hook_block, ShellKind};

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct HookTarget {
    pub shell: ShellKind,
    pub path: PathBuf,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct InstallReport {
    pub shell: ShellKind,
    pub path: PathBuf,
    pub created: bool,
    pub changed: bool,
}

pub fn default_targets() -> Result<Vec<HookTarget>> {
    let home = home_dir()?;
    let xdg_config_home = env::var_os("XDG_CONFIG_HOME").map(PathBuf::from);

    Ok(vec![
        HookTarget {
            shell: ShellKind::Bash,
            path: shell_profile_path(
                ShellKind::Bash,
                env_override_path("ABSOLUTELY_BASH_PROFILE"),
                &home,
                xdg_config_home.as_deref(),
            ),
        },
        HookTarget {
            shell: ShellKind::Zsh,
            path: shell_profile_path(
                ShellKind::Zsh,
                env_override_path("ABSOLUTELY_ZSH_PROFILE"),
                &home,
                xdg_config_home.as_deref(),
            ),
        },
        HookTarget {
            shell: ShellKind::Fish,
            path: shell_profile_path(
                ShellKind::Fish,
                env_override_path("ABSOLUTELY_FISH_CONFIG"),
                &home,
                xdg_config_home.as_deref(),
            ),
        },
        HookTarget {
            shell: ShellKind::Powershell,
            path: shell_profile_path(
                ShellKind::Powershell,
                env_override_path("ABSOLUTELY_POWERSHELL_PROFILE"),
                &home,
                xdg_config_home.as_deref(),
            ),
        },
    ])
}

pub fn install_all_hooks(dry_run: bool) -> Result<Vec<InstallReport>> {
    let targets = default_targets()?;
    install_targets(&targets, dry_run)
}

pub fn uninstall_all_hooks(dry_run: bool) -> Result<Vec<InstallReport>> {
    let targets = default_targets()?;
    uninstall_targets(&targets, dry_run)
}

pub fn install_targets(targets: &[HookTarget], dry_run: bool) -> Result<Vec<InstallReport>> {
    targets
        .iter()
        .map(|target| install_target(target, dry_run))
        .collect()
}

pub fn uninstall_targets(targets: &[HookTarget], dry_run: bool) -> Result<Vec<InstallReport>> {
    targets
        .iter()
        .map(|target| uninstall_target(target, dry_run))
        .collect()
}

pub fn install_target(target: &HookTarget, dry_run: bool) -> Result<InstallReport> {
    let desired = managed_hook_block(target.shell);
    let (updated, created) = apply_managed_block(&target.path, &desired, dry_run)?;
    Ok(InstallReport {
        shell: target.shell,
        path: target.path.clone(),
        created,
        changed: updated,
    })
}

pub fn uninstall_target(target: &HookTarget, dry_run: bool) -> Result<InstallReport> {
    let current = fs::read_to_string(&target.path).unwrap_or_default();
    let created = !target.path.exists();
    let next = remove_managed_block(&current);
    let changed = next != current;
    if changed && !dry_run {
        if next.trim().is_empty() {
            if target.path.exists() {
                fs::remove_file(&target.path)
                    .with_context(|| format!("removing profile {:?}", target.path.display()))?;
            }
        } else {
            if let Some(parent) = target.path.parent() {
                fs::create_dir_all(parent)
                    .with_context(|| format!("creating profile directory {parent:?}"))?;
            }
            fs::write(&target.path, next)
                .with_context(|| format!("writing profile {:?}", target.path.display()))?;
        }
    }
    Ok(InstallReport {
        shell: target.shell,
        path: target.path.clone(),
        created,
        changed,
    })
}

pub fn apply_managed_block(
    path: &Path,
    desired_block: &str,
    dry_run: bool,
) -> Result<(bool, bool)> {
    let current = fs::read_to_string(path).unwrap_or_default();
    let created = !path.exists();
    let next = replace_managed_block(&current, desired_block);
    let changed = next != current;
    if changed && !dry_run {
        if let Some(parent) = path.parent() {
            fs::create_dir_all(parent)
                .with_context(|| format!("creating profile directory {parent:?}"))?;
        }
        fs::write(path, next).with_context(|| format!("writing profile {path:?}"))?;
    }
    Ok((changed, created))
}

pub fn remove_managed_block(current: &str) -> String {
    if let Some((prefix, suffix)) = split_managed_block(current) {
        let mut output = String::with_capacity(prefix.len() + suffix.len());
        output.push_str(prefix);
        output.push_str(suffix);
        if output.is_empty() {
            output
        } else {
            normalize_trailing_newline(output)
        }
    } else {
        current.to_string()
    }
}

pub fn replace_managed_block(current: &str, desired_block: &str) -> String {
    if let Some((prefix, suffix)) = split_managed_block(current) {
        let mut output = String::with_capacity(prefix.len() + desired_block.len() + suffix.len());
        output.push_str(prefix);
        if !prefix.ends_with('\n') && !prefix.is_empty() {
            output.push('\n');
        }
        output.push_str(desired_block);
        output.push_str(suffix);
        normalize_trailing_newline(output)
    } else {
        let mut output = current.to_string();
        if !output.is_empty() && !output.ends_with('\n') {
            output.push('\n');
        }
        output.push_str(desired_block);
        normalize_trailing_newline(output)
    }
}

pub fn split_managed_block(current: &str) -> Option<(&str, &str)> {
    split_managed_block_with_markers(current, MANAGED_BEGIN_MARKER, MANAGED_END_MARKER)
}

fn split_managed_block_with_markers<'a>(
    current: &'a str,
    begin_marker: &'a str,
    end_marker: &'a str,
) -> Option<(&'a str, &'a str)> {
    let begin = current.find(begin_marker)?;
    let begin_line_end = current[begin..]
        .find('\n')
        .map(|offset| begin + offset + 1)
        .unwrap_or(current.len());
    let end = current[begin_line_end..].find(end_marker)? + begin_line_end;
    let suffix_start = current[end..]
        .find('\n')
        .map(|offset| end + offset + 1)
        .unwrap_or(current.len());
    Some((&current[..begin], &current[suffix_start..]))
}

pub fn managed_begin_marker() -> &'static str {
    MANAGED_BEGIN_MARKER
}

pub fn managed_end_marker() -> &'static str {
    MANAGED_END_MARKER
}

pub fn profile_path_for_shell(
    shell: ShellKind,
    home_dir: &Path,
    xdg_config_home: Option<&Path>,
) -> PathBuf {
    let override_key = match shell {
        ShellKind::Bash => "ABSOLUTELY_BASH_PROFILE",
        ShellKind::Zsh => "ABSOLUTELY_ZSH_PROFILE",
        ShellKind::Fish => "ABSOLUTELY_FISH_CONFIG",
        ShellKind::Powershell => "ABSOLUTELY_POWERSHELL_PROFILE",
    };
    if let Some(path) = env_override_path(override_key) {
        return path;
    }
    shell_profile_path(shell, None, home_dir, xdg_config_home)
}

pub fn shell_profile_path(
    shell: ShellKind,
    override_path: Option<PathBuf>,
    home_dir: &Path,
    xdg_config_home: Option<&Path>,
) -> PathBuf {
    if let Some(path) = override_path {
        return path;
    }
    match shell {
        ShellKind::Bash => home_dir.join(".bashrc"),
        ShellKind::Zsh => home_dir.join(".zshrc"),
        ShellKind::Fish => {
            let config_home = xdg_config_home
                .map(Path::to_path_buf)
                .unwrap_or_else(|| home_dir.join(".config"));
            config_home.join("fish").join("config.fish")
        }
        ShellKind::Powershell => {
            let config_home = xdg_config_home
                .map(Path::to_path_buf)
                .unwrap_or_else(|| home_dir.join(".config"));
            config_home
                .join("powershell")
                .join("Microsoft.PowerShell_profile.ps1")
        }
    }
}

fn home_dir() -> Result<PathBuf> {
    if let Some(home) = env::var_os("HOME").or_else(|| env::var_os("USERPROFILE")) {
        return Ok(PathBuf::from(home));
    }
    anyhow::bail!("HOME or USERPROFILE is not set")
}

fn env_override_path(key: &str) -> Option<PathBuf> {
    env::var_os(key).map(PathBuf::from)
}

fn normalize_trailing_newline(mut value: String) -> String {
    if !value.ends_with('\n') {
        value.push('\n');
    }
    value
}

const MANAGED_BEGIN_MARKER: &str = "# >>> Tracehouse managed hook";
const MANAGED_END_MARKER: &str = "# <<< Tracehouse managed hook";

#[cfg(test)]
mod tests {
    use super::*;
    use std::fs;
    use std::path::Path;
    use tempfile::tempdir;

    #[test]
    fn shell_profile_path_uses_expected_defaults() {
        let home = Path::new("/home/tester");
        let xdg = Path::new("/home/tester/.config");

        assert_eq!(
            shell_profile_path(ShellKind::Bash, None, home, None),
            home.join(".bashrc")
        );
        assert_eq!(
            shell_profile_path(ShellKind::Zsh, None, home, None),
            home.join(".zshrc")
        );
        assert_eq!(
            shell_profile_path(ShellKind::Fish, None, home, Some(xdg)),
            xdg.join("fish").join("config.fish")
        );
        assert_eq!(
            shell_profile_path(ShellKind::Powershell, None, home, Some(xdg)),
            xdg.join("powershell")
                .join("Microsoft.PowerShell_profile.ps1")
        );
        assert_eq!(
            shell_profile_path(
                ShellKind::Bash,
                Some(PathBuf::from("/tmp/custom-bashrc")),
                home,
                None
            ),
            PathBuf::from("/tmp/custom-bashrc")
        );
    }

    #[test]
    fn replace_managed_block_preserves_suffix_and_replaces_only_once() {
        let current = format!(
            "export PATH=\"$PATH\"\n{}\nold collector\n{}\n\nalias ll='ls -l'\n",
            managed_begin_marker(),
            managed_end_marker()
        );
        let desired = format!(
            "{}\nnew collector\n{}\n",
            managed_begin_marker(),
            managed_end_marker()
        );

        let output = replace_managed_block(&current, &desired);

        let expected = format!(
            "export PATH=\"$PATH\"\n{}\nnew collector\n{}\n\nalias ll='ls -l'\n",
            managed_begin_marker(),
            managed_end_marker()
        );
        assert_eq!(output, expected);
        assert_eq!(output.matches(managed_begin_marker()).count(), 1);
        assert_eq!(output.matches(managed_end_marker()).count(), 1);
    }

    #[test]
    fn replace_managed_block_handles_real_managed_hook_blocks() {
        let current = format!(
            "export PATH=\"$PATH\"\n{}trailer\n",
            managed_hook_block(ShellKind::Bash)
        );
        let desired = managed_hook_block(ShellKind::Zsh);

        let output = replace_managed_block(&current, &desired);

        let expected = format!(
            "export PATH=\"$PATH\"\n{}trailer\n",
            managed_hook_block(ShellKind::Zsh)
        );
        assert_eq!(output, expected);
    }

    #[test]
    fn remove_managed_block_preserves_suffix_and_removes_only_once() {
        let current = format!(
            "export PATH=\"$PATH\"\n{}trailer\n",
            managed_hook_block(ShellKind::Bash)
        );

        let output = remove_managed_block(&current);

        let expected = "export PATH=\"$PATH\"\ntrailer\n";
        assert_eq!(output, expected);
        assert_eq!(output.matches(managed_begin_marker()).count(), 0);
        assert_eq!(output.matches(managed_end_marker()).count(), 0);
    }

    #[test]
    fn install_target_writes_managed_block_to_new_file() {
        let tempdir = tempdir().expect("tempdir");
        let profile_path = tempdir.path().join("dotfiles").join(".bashrc");
        let target = HookTarget {
            shell: ShellKind::Bash,
            path: profile_path.clone(),
        };

        let report = install_target(&target, false).expect("install target");

        assert_eq!(report.shell, ShellKind::Bash);
        assert_eq!(report.path, profile_path);
        assert!(report.created);
        assert!(report.changed);
        assert!(profile_path.parent().expect("parent").exists());
        assert_eq!(
            fs::read_to_string(&profile_path).expect("profile"),
            managed_hook_block(ShellKind::Bash)
        );
    }

    #[test]
    fn install_target_updates_existing_file_without_duplication() {
        let tempdir = tempdir().expect("tempdir");
        let profile_path = tempdir.path().join(".zshrc");
        let existing = format!(
            "source ~/.zshenv\n{}\nold collector\n{}\nsuffix\n",
            managed_begin_marker(),
            managed_end_marker()
        );
        fs::write(&profile_path, existing).expect("seed profile");
        let target = HookTarget {
            shell: ShellKind::Zsh,
            path: profile_path.clone(),
        };

        let report = install_target(&target, false).expect("install target");

        assert!(!report.created);
        assert!(report.changed);
        let contents = fs::read_to_string(&profile_path).expect("profile");
        let expected = format!(
            "source ~/.zshenv\n{}suffix\n",
            managed_hook_block(ShellKind::Zsh)
        );
        assert_eq!(contents, expected);
        assert_eq!(contents.matches(managed_begin_marker()).count(), 1);
        assert_eq!(contents.matches(managed_end_marker()).count(), 1);
    }

    #[test]
    fn uninstall_target_removes_managed_block_and_file_when_empty() {
        let tempdir = tempdir().expect("tempdir");
        let profile_path = tempdir.path().join(".bashrc");
        fs::write(&profile_path, managed_hook_block(ShellKind::Bash)).expect("seed profile");
        let target = HookTarget {
            shell: ShellKind::Bash,
            path: profile_path.clone(),
        };

        let report = uninstall_target(&target, false).expect("uninstall target");

        assert!(!report.created);
        assert!(report.changed);
        assert!(!profile_path.exists());
    }

    #[test]
    fn uninstall_target_dry_run_does_not_write_file() {
        let tempdir = tempdir().expect("tempdir");
        let profile_path = tempdir
            .path()
            .join(".config")
            .join("fish")
            .join("config.fish");
        if let Some(parent) = profile_path.parent() {
            fs::create_dir_all(parent).expect("parent dirs");
        }
        fs::write(
            &profile_path,
            format!("before\n{}\nafter\n", managed_hook_block(ShellKind::Fish)),
        )
        .expect("seed profile");
        let target = HookTarget {
            shell: ShellKind::Fish,
            path: profile_path.clone(),
        };

        let report = uninstall_target(&target, true).expect("uninstall target");

        assert!(!report.created);
        assert!(report.changed);
        assert!(profile_path.exists());
        assert!(fs::read_to_string(&profile_path)
            .expect("profile")
            .contains("Tracehouse fish hook"));
    }

    #[test]
    fn install_target_dry_run_does_not_write_file() {
        let tempdir = tempdir().expect("tempdir");
        let profile_path = tempdir
            .path()
            .join(".config")
            .join("fish")
            .join("config.fish");
        let target = HookTarget {
            shell: ShellKind::Fish,
            path: profile_path.clone(),
        };

        let report = install_target(&target, true).expect("install target");

        assert!(report.created);
        assert!(report.changed);
        assert!(!profile_path.exists());
    }
}
