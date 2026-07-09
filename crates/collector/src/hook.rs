use clap::ValueEnum;

use crate::install::{managed_begin_marker, managed_end_marker};

#[derive(Debug, Clone, Copy, PartialEq, Eq, ValueEnum)]
pub enum ShellKind {
    Bash,
    Zsh,
    Fish,
    Powershell,
}

pub fn render_hook(shell: ShellKind) -> &'static str {
    match shell {
        ShellKind::Bash => BASH_HOOK,
        ShellKind::Zsh => ZSH_HOOK,
        ShellKind::Fish => FISH_HOOK,
        ShellKind::Powershell => POWERSHELL_HOOK,
    }
}

pub fn shell_name(shell: ShellKind) -> &'static str {
    match shell {
        ShellKind::Bash => "bash",
        ShellKind::Zsh => "zsh",
        ShellKind::Fish => "fish",
        ShellKind::Powershell => "powershell",
    }
}

pub fn managed_hook_block(shell: ShellKind) -> String {
    format!(
        "{} ({})\n{}\n{} ({})\n",
        managed_begin_marker(),
        shell_name(shell),
        render_hook(shell),
        managed_end_marker(),
        shell_name(shell)
    )
}

const BASH_HOOK: &str = r#"# Tracehouse bash hook
if [[ -z "${TRACEHOUSE_COLLECTOR_BIN:-}" ]]; then
  export TRACEHOUSE_COLLECTOR_BIN="tracehouse-collector"
fi
if [[ -z "${ABSOLUTELY_SESSION_ID:-}" ]]; then
  export ABSOLUTELY_SESSION_ID="$("$TRACEHOUSE_COLLECTOR_BIN" session-id 2>/dev/null || true)"
fi

__absolutely_capture_active=""
__absolutely_capture_id=""
export ABSOLUTELY_CAPTURE_ID=""
export ABSOLUTELY_TRANSCRIPT_FILE=""

__absolutely_transcript_file() {
  local label="$1"
  local suffix="${label// /-}"
  local transcript_file
  transcript_file="$(mktemp "${TMPDIR:-/tmp}/absolutely-${suffix}.XXXXXX")" || return 1
  rm -f "$transcript_file"
  printf '%s' "$transcript_file"
}

__absolutely_run_agent_command() {
  local label="$1"
  local binary="$2"
  shift 2
  if [[ -z "${ABSOLUTELY_CAPTURE_ID:-}" ]]; then
    command "$binary" "$@"
    return $?
  fi
  local transcript_file
  transcript_file="$(__absolutely_transcript_file "$label")" || return $?
  export ABSOLUTELY_TRANSCRIPT_FILE="$transcript_file"
  "$TRACEHOUSE_COLLECTOR_BIN" agent-run -- "$binary" "$@"
}

__absolutely_codex() { __absolutely_run_agent_command "Codex CLI" codex "$@"; }
__absolutely_claude() { __absolutely_run_agent_command "Claude Code" claude "$@"; }
__absolutely_aider() { __absolutely_run_agent_command "Aider" aider "$@"; }
__absolutely_gemini() { __absolutely_run_agent_command "Gemini CLI" gemini "$@"; }
__absolutely_cursor() { __absolutely_run_agent_command "Cursor Agent" cursor "$@"; }
__absolutely_cursor_agent() { __absolutely_run_agent_command "Cursor Agent" cursor-agent "$@"; }
__absolutely_claude_code() { __absolutely_run_agent_command "Claude Code" claude-code "$@"; }
__absolutely_codex_cli() { __absolutely_run_agent_command "Codex CLI" codex-cli "$@"; }
__absolutely_gemini_cli() { __absolutely_run_agent_command "Gemini CLI" gemini-cli "$@"; }

alias codex='__absolutely_codex'
alias claude='__absolutely_claude'
alias aider='__absolutely_aider'
alias gemini='__absolutely_gemini'
alias cursor='__absolutely_cursor'
alias cursor-agent='__absolutely_cursor_agent'
alias claude-code='__absolutely_claude_code'
alias codex-cli='__absolutely_codex_cli'
alias gemini-cli='__absolutely_gemini_cli'

__absolutely_start_command_capture() {
  if [[ -n "${__absolutely_capture_active:-}" ]]; then
    return 0
  fi
  export ABSOLUTELY_CAPTURE_ID=""
  export ABSOLUTELY_TRANSCRIPT_FILE=""
  if [[ -n "${ABSOLUTELY_PAUSED:-}" && "${ABSOLUTELY_PAUSED}" != "0" ]]; then
    return 0
  fi
  case "${BASH_COMMAND:-}" in
    __absolutely_*|tracehouse-collector*)
      return 0
      ;;
  esac
  __absolutely_capture_active=1
  __absolutely_capture_id="$("$TRACEHOUSE_COLLECTOR_BIN" start --shell bash --session-id "$ABSOLUTELY_SESSION_ID" --cwd "$PWD" 2>/dev/null || true)"
  export ABSOLUTELY_CAPTURE_ID="$__absolutely_capture_id"
}

__absolutely_finish_command_capture() {
  local exit_code="$?"
  if [[ -n "${__absolutely_capture_active:-}" && -n "${__absolutely_capture_id:-}" ]]; then
    local command_line
    command_line="$(fc -ln -1 2>/dev/null || true)"
    "$TRACEHOUSE_COLLECTOR_BIN" finish \
      --capture-id "$__absolutely_capture_id" \
      --session-id "$ABSOLUTELY_SESSION_ID" \
      --shell bash \
      --exit-code "$exit_code" \
      --cwd "$PWD" \
      --command "$command_line" >/dev/null 2>&1 || true
  fi
  __absolutely_capture_active=""
  __absolutely_capture_id=""
  export ABSOLUTELY_CAPTURE_ID=""
  export ABSOLUTELY_TRANSCRIPT_FILE=""
}

trap '__absolutely_start_command_capture' DEBUG
if [[ -n "${PROMPT_COMMAND:-}" ]]; then
  PROMPT_COMMAND="__absolutely_finish_command_capture; ${PROMPT_COMMAND}"
else
  PROMPT_COMMAND="__absolutely_finish_command_capture"
fi
"#;

const ZSH_HOOK: &str = r#"# Tracehouse zsh hook
if [[ -z "${TRACEHOUSE_COLLECTOR_BIN:-}" ]]; then
  export TRACEHOUSE_COLLECTOR_BIN="tracehouse-collector"
fi
if [[ -z "${ABSOLUTELY_SESSION_ID:-}" ]]; then
  export ABSOLUTELY_SESSION_ID="$("$TRACEHOUSE_COLLECTOR_BIN" session-id 2>/dev/null || true)"
fi

typeset -g __absolutely_capture_active=""
typeset -g __absolutely_capture_id=""
typeset -g __absolutely_capture_command=""
export ABSOLUTELY_CAPTURE_ID=""
export ABSOLUTELY_TRANSCRIPT_FILE=""

function __absolutely_transcript_file() {
  local label="$1"
  local suffix="${label// /-}"
  local transcript_file
  transcript_file="$(mktemp "${TMPDIR:-/tmp}/absolutely-${suffix}.XXXXXX")" || return 1
  rm -f "$transcript_file"
  printf '%s' "$transcript_file"
}

function __absolutely_run_agent_command() {
  local label="$1"
  local binary="$2"
  shift 2
  if [[ -z "${ABSOLUTELY_CAPTURE_ID:-}" ]]; then
    command "$binary" "$@"
    return $?
  fi
  local transcript_file
  transcript_file="$(__absolutely_transcript_file "$label")" || return $?
  export ABSOLUTELY_TRANSCRIPT_FILE="$transcript_file"
  "$TRACEHOUSE_COLLECTOR_BIN" agent-run -- "$binary" "$@"
}

function __absolutely_codex() { __absolutely_run_agent_command "Codex CLI" codex "$@"; }
function __absolutely_claude() { __absolutely_run_agent_command "Claude Code" claude "$@"; }
function __absolutely_aider() { __absolutely_run_agent_command "Aider" aider "$@"; }
function __absolutely_gemini() { __absolutely_run_agent_command "Gemini CLI" gemini "$@"; }
function __absolutely_cursor() { __absolutely_run_agent_command "Cursor Agent" cursor "$@"; }
function __absolutely_cursor_agent() { __absolutely_run_agent_command "Cursor Agent" cursor-agent "$@"; }
function __absolutely_claude_code() { __absolutely_run_agent_command "Claude Code" claude-code "$@"; }
function __absolutely_codex_cli() { __absolutely_run_agent_command "Codex CLI" codex-cli "$@"; }
function __absolutely_gemini_cli() { __absolutely_run_agent_command "Gemini CLI" gemini-cli "$@"; }

alias codex='__absolutely_codex'
alias claude='__absolutely_claude'
alias aider='__absolutely_aider'
alias gemini='__absolutely_gemini'
alias cursor='__absolutely_cursor'
alias cursor-agent='__absolutely_cursor_agent'
alias claude-code='__absolutely_claude_code'
alias codex-cli='__absolutely_codex_cli'
alias gemini-cli='__absolutely_gemini_cli'

function __absolutely_start_command_capture() {
  if [[ -n "${__absolutely_capture_active:-}" ]]; then
    return 0
  fi
  export ABSOLUTELY_CAPTURE_ID=""
  export ABSOLUTELY_TRANSCRIPT_FILE=""
  if [[ -n "${ABSOLUTELY_PAUSED:-}" && "${ABSOLUTELY_PAUSED}" != "0" ]]; then
    return 0
  fi
  __absolutely_capture_active=1
  __absolutely_capture_command="$1"
  __absolutely_capture_id="$("$TRACEHOUSE_COLLECTOR_BIN" start --shell zsh --session-id "$ABSOLUTELY_SESSION_ID" --cwd "$PWD" --command "$1" 2>/dev/null || true)"
  export ABSOLUTELY_CAPTURE_ID="$__absolutely_capture_id"
}

function __absolutely_finish_command_capture() {
  local exit_code="$?"
  if [[ -n "${__absolutely_capture_active:-}" && -n "${__absolutely_capture_id:-}" ]]; then
    "$TRACEHOUSE_COLLECTOR_BIN" finish \
      --capture-id "$__absolutely_capture_id" \
      --session-id "$ABSOLUTELY_SESSION_ID" \
      --shell zsh \
      --exit-code "$exit_code" \
      --cwd "$PWD" \
      --command "$__absolutely_capture_command" >/dev/null 2>&1 || true
  fi
  __absolutely_capture_active=""
  __absolutely_capture_id=""
  __absolutely_capture_command=""
  export ABSOLUTELY_CAPTURE_ID=""
  export ABSOLUTELY_TRANSCRIPT_FILE=""
}

autoload -Uz add-zsh-hook
add-zsh-hook preexec __absolutely_start_command_capture
add-zsh-hook precmd __absolutely_finish_command_capture
"#;

const FISH_HOOK: &str = r#"# Tracehouse fish hook
if not set -q TRACEHOUSE_COLLECTOR_BIN
    set -gx TRACEHOUSE_COLLECTOR_BIN tracehouse-collector
end
if not set -q ABSOLUTELY_SESSION_ID
    set -gx ABSOLUTELY_SESSION_ID (command $TRACEHOUSE_COLLECTOR_BIN session-id 2>/dev/null)
end

set -g __absolutely_capture_active 0
set -g __absolutely_capture_id ""
set -g __absolutely_capture_command ""
set -gx ABSOLUTELY_CAPTURE_ID ""
set -gx ABSOLUTELY_TRANSCRIPT_FILE ""

function __absolutely_transcript_file
    set -l label $argv[1]
    set -l suffix (string replace -a ' ' '-' -- $label)
    set -l temp_dir $TMPDIR
    if test -z "$temp_dir"
        set temp_dir /tmp
    end
    set -l transcript_file (mktemp "$temp_dir/absolutely-$suffix.XXXXXX")
    or return 1
    command rm -f "$transcript_file"
    printf '%s' "$transcript_file"
end

function __absolutely_run_agent_command
    set -l label $argv[1]
    set -l binary $argv[2]
    set -l args $argv[3..-1]
    if test -z "$ABSOLUTELY_CAPTURE_ID"
        command "$binary" $args
        return $status
    end
    set -l transcript_file (__absolutely_transcript_file "$label")
    or return 1
    set -gx ABSOLUTELY_TRANSCRIPT_FILE "$transcript_file"
    command $TRACEHOUSE_COLLECTOR_BIN agent-run -- "$binary" $args
end

function codex
    __absolutely_run_agent_command "Codex CLI" codex $argv
end

function claude
    __absolutely_run_agent_command "Claude Code" claude $argv
end

function aider
    __absolutely_run_agent_command "Aider" aider $argv
end

function gemini
    __absolutely_run_agent_command "Gemini CLI" gemini $argv
end

function cursor
    __absolutely_run_agent_command "Cursor Agent" cursor $argv
end

function cursor-agent
    __absolutely_run_agent_command "Cursor Agent" cursor-agent $argv
end

function claude-code
    __absolutely_run_agent_command "Claude Code" claude-code $argv
end

function codex-cli
    __absolutely_run_agent_command "Codex CLI" codex-cli $argv
end

function gemini-cli
    __absolutely_run_agent_command "Gemini CLI" gemini-cli $argv
end

function __absolutely_start_command_capture --on-event fish_preexec
    set -l command_line $argv[1]
    if test "$__absolutely_capture_active" = "1"
        return
    end
    set -gx ABSOLUTELY_CAPTURE_ID ""
    set -gx ABSOLUTELY_TRANSCRIPT_FILE ""
    if test -n "$ABSOLUTELY_PAUSED"
        return
    end
    set -g __absolutely_capture_active 1
    set -g __absolutely_capture_command "$command_line"
    set -g __absolutely_capture_id (command $TRACEHOUSE_COLLECTOR_BIN start --shell fish --session-id "$ABSOLUTELY_SESSION_ID" --cwd (pwd) --command "$command_line" 2>/dev/null)
    set -gx ABSOLUTELY_CAPTURE_ID "$__absolutely_capture_id"
end

function __absolutely_finish_command_capture --on-event fish_postexec
    set -l exit_code $status
    if test "$__absolutely_capture_active" = "1"
        if test -n "$__absolutely_capture_id"
            command $TRACEHOUSE_COLLECTOR_BIN finish --capture-id "$__absolutely_capture_id" --session-id "$ABSOLUTELY_SESSION_ID" --shell fish --exit-code $exit_code --cwd (pwd) --command "$__absolutely_capture_command" >/dev/null 2>&1
        end
        set -g __absolutely_capture_active 0
        set -g __absolutely_capture_id ""
        set -g __absolutely_capture_command ""
        set -gx ABSOLUTELY_CAPTURE_ID ""
        set -gx ABSOLUTELY_TRANSCRIPT_FILE ""
    end
end
"#;

const POWERSHELL_HOOK: &str = r#"# Tracehouse PowerShell hook
if ([string]::IsNullOrWhiteSpace($env:TRACEHOUSE_COLLECTOR_BIN)) {
    $env:TRACEHOUSE_COLLECTOR_BIN = 'tracehouse-collector'
}
if ([string]::IsNullOrWhiteSpace($env:ABSOLUTELY_SESSION_ID)) {
    $env:ABSOLUTELY_SESSION_ID = & $env:TRACEHOUSE_COLLECTOR_BIN session-id 2>$null
}

$script:AbsolutelyPendingCaptureId = $null
$script:AbsolutelyPendingCommand = $null
$script:AbsolutelyOriginalPrompt = $null
$env:ABSOLUTELY_CAPTURE_ID = ""
$env:ABSOLUTELY_TRANSCRIPT_FILE = ""

function Invoke-AbsolutelyAgentCommand {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ToolName,
        [Parameter(Mandatory = $true)]
        [string]$Binary,
        [Parameter(ValueFromRemainingArguments = $true)]
        [string[]]$Args
    )

    if ([string]::IsNullOrWhiteSpace($env:ABSOLUTELY_CAPTURE_ID)) {
        $resolved = Get-Command $Binary -CommandType Application -ErrorAction Stop
        & $resolved @Args
        return $LASTEXITCODE
    }

    $transcriptFile = [System.IO.Path]::GetTempFileName()
    Remove-Item -LiteralPath $transcriptFile -Force
    $env:ABSOLUTELY_TRANSCRIPT_FILE = $transcriptFile

    try {
        Start-Transcript -Path $transcriptFile -Force | Out-Null
        try {
            $resolved = Get-Command $Binary -CommandType Application -ErrorAction Stop
            & $resolved @Args
        } finally {
            Stop-Transcript | Out-Null
        }
    } catch {
        $env:ABSOLUTELY_TRANSCRIPT_FILE = ""
        Remove-Item -LiteralPath $transcriptFile -Force -ErrorAction SilentlyContinue
        $resolved = Get-Command $Binary -CommandType Application -ErrorAction Stop
        & $resolved @Args
    }

    return $LASTEXITCODE
}

function codex { Invoke-AbsolutelyAgentCommand -ToolName 'Codex CLI' -Binary 'codex' @args }
function claude { Invoke-AbsolutelyAgentCommand -ToolName 'Claude Code' -Binary 'claude' @args }
function aider { Invoke-AbsolutelyAgentCommand -ToolName 'Aider' -Binary 'aider' @args }
function gemini { Invoke-AbsolutelyAgentCommand -ToolName 'Gemini CLI' -Binary 'gemini' @args }
function cursor { Invoke-AbsolutelyAgentCommand -ToolName 'Cursor Agent' -Binary 'cursor' @args }
function 'cursor-agent' { Invoke-AbsolutelyAgentCommand -ToolName 'Cursor Agent' -Binary 'cursor-agent' @args }
function 'claude-code' { Invoke-AbsolutelyAgentCommand -ToolName 'Claude Code' -Binary 'claude-code' @args }
function 'codex-cli' { Invoke-AbsolutelyAgentCommand -ToolName 'Codex CLI' -Binary 'codex-cli' @args }
function 'gemini-cli' { Invoke-AbsolutelyAgentCommand -ToolName 'Gemini CLI' -Binary 'gemini-cli' @args }

if (Get-Module -ListAvailable PSReadLine) {
    Set-PSReadLineOption -AddToHistoryHandler {
        param($line)
        if ([string]::IsNullOrWhiteSpace($line)) {
            return $false
        }
        $env:ABSOLUTELY_CAPTURE_ID = ""
        $env:ABSOLUTELY_TRANSCRIPT_FILE = ""
        if ($env:ABSOLUTELY_PAUSED -and $env:ABSOLUTELY_PAUSED -ne '0') {
            $env:ABSOLUTELY_CAPTURE_ID = ""
            return $true
        }
        $script:AbsolutelyPendingCommand = $line
        $script:AbsolutelyPendingCaptureId = & $env:TRACEHOUSE_COLLECTOR_BIN start --shell powershell --session-id $env:ABSOLUTELY_SESSION_ID --cwd (Get-Location).Path --command $line 2>$null
        $env:ABSOLUTELY_CAPTURE_ID = $script:AbsolutelyPendingCaptureId
        return $true
    }
}

try {
    $script:AbsolutelyOriginalPrompt = (Get-Command prompt -ErrorAction Stop).ScriptBlock
} catch {
    $script:AbsolutelyOriginalPrompt = $null
}

function prompt {
    $exitCode = if ($LASTEXITCODE -ne $null) { $LASTEXITCODE } else { 0 }
    if ($script:AbsolutelyPendingCaptureId) {
        & $env:TRACEHOUSE_COLLECTOR_BIN finish --capture-id $script:AbsolutelyPendingCaptureId --session-id $env:ABSOLUTELY_SESSION_ID --shell powershell --exit-code $exitCode --cwd (Get-Location).Path --command $script:AbsolutelyPendingCommand 2>$null | Out-Null
        $script:AbsolutelyPendingCaptureId = $null
        $script:AbsolutelyPendingCommand = $null
        $env:ABSOLUTELY_CAPTURE_ID = ""
        $env:ABSOLUTELY_TRANSCRIPT_FILE = ""
    }
    if ($script:AbsolutelyOriginalPrompt) {
        & $script:AbsolutelyOriginalPrompt
    } else {
        "PS $((Get-Location).Path)> "
    }
}
"#;
