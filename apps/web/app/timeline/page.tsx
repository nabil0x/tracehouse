import Link from "next/link";

import {
  DashboardShell,
  EmptyState,
  MiniStat,
  SectionHeader,
  SessionMetric,
} from "@/components/dashboard-shell";
import { CommandTranscript } from "@/components/command-transcript";
import { getTimeline, type CommandRecord } from "@/lib/api";
import { formatCount, formatDuration, formatTimestamp } from "@/lib/format";

export const dynamic = "force-dynamic";

type SearchParams = Record<string, string | string[] | undefined>;

type TimelineFilters = {
  query?: string;
  host?: string;
  session_key?: string;
  repository?: string;
  git_commit_hash?: string;
  shell?: string;
  exit_code?: string;
  actor_type?: string;
  actor_name?: string;
  cwd?: string;
  started_after?: string;
  started_before?: string;
};

function firstSearchParam(value: string | string[] | undefined): string | undefined {
  if (Array.isArray(value)) {
    return value[0];
  }
  return value;
}

function normalizeFilters(searchParams: SearchParams): TimelineFilters {
  return {
    query: firstSearchParam(searchParams.query)?.trim() || undefined,
    host: firstSearchParam(searchParams.host)?.trim() || undefined,
    session_key: firstSearchParam(searchParams.session_key)?.trim() || undefined,
    repository: firstSearchParam(searchParams.repository)?.trim() || undefined,
    git_commit_hash: firstSearchParam(searchParams.git_commit_hash)?.trim() || undefined,
    shell: firstSearchParam(searchParams.shell)?.trim() || undefined,
    exit_code: firstSearchParam(searchParams.exit_code)?.trim() || undefined,
    actor_type: firstSearchParam(searchParams.actor_type)?.trim() || undefined,
    actor_name: firstSearchParam(searchParams.actor_name)?.trim() || undefined,
    cwd: firstSearchParam(searchParams.cwd)?.trim() || undefined,
    started_after: firstSearchParam(searchParams.started_after)?.trim() || undefined,
    started_before: firstSearchParam(searchParams.started_before)?.trim() || undefined,
  };
}

function parseExitCode(value?: string): number | undefined {
  if (!value) {
    return undefined;
  }
  const parsed = Number.parseInt(value, 10);
  return Number.isNaN(parsed) ? undefined : parsed;
}

function filterCount(filters: TimelineFilters): number {
  return [
    filters.query,
    filters.host,
    filters.session_key,
    filters.repository,
    filters.git_commit_hash,
    filters.shell,
    filters.exit_code,
    filters.actor_type,
    filters.actor_name,
    filters.cwd,
    filters.started_after,
    filters.started_before,
  ].filter(Boolean).length;
}

function uniqueCount(commands: CommandRecord[], pick: (command: CommandRecord) => string | null | undefined) {
  return new Set(commands.map(pick).filter(Boolean)).size;
}

function summarizeFailureRate(commands: CommandRecord[]) {
  const failures = commands.filter((command) => command.exit_code !== 0).length;
  return { failures, successes: commands.length - failures };
}

export default async function TimelinePage(props: { searchParams: Promise<SearchParams> }) {
  const searchParams = await props.searchParams;
  const filters = normalizeFilters(searchParams);
  const exitCodeFilter = parseExitCode(filters.exit_code);
  const result = await getTimeline({
    query: filters.query,
    host: filters.host,
    session_key: filters.session_key,
    repository: filters.repository,
    git_commit_hash: filters.git_commit_hash,
    shell: filters.shell,
    exit_code: exitCodeFilter,
    actor_type: filters.actor_type,
    actor_name: filters.actor_name,
    cwd: filters.cwd,
    started_after: filters.started_after,
    started_before: filters.started_before,
    limit: 100,
  });

  const commands = result.items;
  const counts = summarizeFailureRate(commands);
  const sessionCount = uniqueCount(commands, (command) => command.session_key);
  const repositoryCount = uniqueCount(commands, (command) => command.repository_name || command.repository_root);
  const actorCount = uniqueCount(commands, (command) => command.actor_name);
  const visibleCount = commands.length;
  const filterTotal = filterCount(filters);
  const latest = commands[0];

  return (
    <DashboardShell
      active="timeline"
      eyebrow="Timeline"
      title="A live command ledger for the workday."
      description="Search the terminal trail, spot failures, and jump from a command straight into the session that produced it."
      aside={
        <div className="statusGrid">
          <MiniStat label="Matched" value={formatCount(result.total)} />
          <MiniStat label="Visible" value={formatCount(visibleCount)} />
          <MiniStat label="Filters" value={formatCount(filterTotal)} />
          <MiniStat label="Failures" value={formatCount(counts.failures)} />
        </div>
      }
    >
      {result.error ? (
        <section className="card errorCard">
          <p className="errorTitle">Timeline data is unavailable</p>
          <p className="errorDetail">{result.error}</p>
        </section>
      ) : null}

      <section className="card timelineFilterCard">
        <form action="/timeline" method="get" className="timelineFilters">
          <div className="timelineFilterGrid">
            <label className="filterField">
              <span className="filterLabel">Query</span>
              <input
                name="query"
                type="search"
                defaultValue={filters.query}
                placeholder="auth bug, docker, CUDA..."
                className="filterInput"
              />
            </label>

            <label className="filterField">
              <span className="filterLabel">Session key</span>
              <input
                name="session_key"
                defaultValue={filters.session_key}
                placeholder="session-1"
                className="filterInput"
              />
            </label>

            <label className="filterField">
              <span className="filterLabel">Repository</span>
              <input
                name="repository"
                defaultValue={filters.repository}
                placeholder="/work/backend"
                className="filterInput"
              />
            </label>

            <label className="filterField">
              <span className="filterLabel">Commit hash</span>
              <input
                name="git_commit_hash"
                defaultValue={filters.git_commit_hash}
                placeholder="deadbeef..."
                className="filterInput"
              />
            </label>

            <label className="filterField">
              <span className="filterLabel">Host</span>
              <input name="host" defaultValue={filters.host} placeholder="laptop" className="filterInput" />
            </label>

            <label className="filterField">
              <span className="filterLabel">Shell</span>
              <input name="shell" defaultValue={filters.shell} placeholder="bash" className="filterInput" />
            </label>

            <label className="filterField">
              <span className="filterLabel">Actor</span>
              <input
                name="actor_name"
                defaultValue={filters.actor_name}
                placeholder="Codex CLI"
                className="filterInput"
              />
            </label>

            <label className="filterField">
              <span className="filterLabel">Actor type</span>
              <select name="actor_type" defaultValue={filters.actor_type ?? ""} className="filterInput">
                <option value="">Any</option>
                <option value="human">Human</option>
                <option value="agent">Agent</option>
              </select>
            </label>

            <label className="filterField">
              <span className="filterLabel">Exit code</span>
              <input
                name="exit_code"
                defaultValue={filters.exit_code}
                placeholder="0"
                inputMode="numeric"
                className="filterInput"
              />
            </label>
          </div>

          <div className="filterActions">
            <button type="submit" className="pill filterButton">
              Apply filters
            </button>
            <Link href="/timeline" className="pill">
              Reset
            </Link>
          </div>
        </form>
      </section>

      <section className="metricGrid">
        <SessionMetric
          label="Commands loaded"
          value={formatCount(visibleCount)}
          detail={
            result.total > visibleCount
              ? `showing the newest ${visibleCount} of ${result.total} matches`
              : "all matching commands are visible"
          }
        />
        <SessionMetric
          label="Sessions"
          value={formatCount(sessionCount)}
          detail="unique shell sessions in the visible command set"
        />
        <SessionMetric
          label="Repositories"
          value={formatCount(repositoryCount)}
          detail="distinct repositories across the visible commands"
        />
        <SessionMetric
          label="Agents"
          value={formatCount(actorCount)}
          detail="distinct command authors in the timeline preview"
        />
      </section>

      <SectionHeader
        title="Command timeline"
        detail={
          filterTotal > 0
            ? "Filtered view of the command stream."
            : "Unfiltered view of recent terminal activity."
        }
        action={
          <Link href="/sessions" className="subtleLink">
            View sessions
          </Link>
        }
      />

      <div className="commandList">
        {commands.length > 0 ? (
          commands.map((command, index) => {
            const redactedCount = command.redaction_findings.length;
            return (
              <article key={command.id} className="card commandItem" data-exit={String(command.exit_code)}>
                <div className="commandTop">
                  <div>
                    <p className="commandIndex">Event {index + 1}</p>
                    <p className="commandText">{command.command}</p>
                  </div>
                  <div className="commandExit">exit {command.exit_code}</div>
                </div>

                <div className="commandMetaRow">
                  <span className="pill">{formatTimestamp(command.timestamp_start)}</span>
                  <span className="pill">{formatDuration(command.duration_ms)}</span>
                  <span className="pill">{command.shell}</span>
                  <span className="pill">{command.host}</span>
                  {command.repository_name ? <span className="pill">{command.repository_name}</span> : null}
                  {command.actor_name ? <span className="pill">{command.actor_name}</span> : null}
                  <Link href={`/sessions/${encodeURIComponent(command.session_key)}`} className="pill">
                    Session {command.session_key}
                  </Link>
                  {redactedCount > 0 ? <span className="pill">{redactedCount} redactions</span> : null}
                </div>

                <div className="timelineMetaRow">
                  <span className="timelineMetaPill">cwd {command.cwd}</span>
                  {command.git_branch ? <span className="timelineMetaPill">branch {command.git_branch}</span> : null}
                  {command.git_commit_hash ? (
                    <span className="timelineMetaPill">commit {command.git_commit_hash.slice(0, 12)}</span>
                  ) : null}
                </div>

                <CommandTranscript
                  title="Transcript"
                  stdout={command.stdout}
                  stderr={command.stderr}
                  note={<span>Captured from the terminal session that produced this event.</span>}
                />
              </article>
            );
          })
        ) : (
          <EmptyState
            title="No commands match these filters"
            detail="Broaden the query, clear the filters, or start the collector and run a few commands."
          />
        )}
      </div>

      {latest ? (
        <section className="card cardStrong detailHeaderCard">
          <div className="detailHeaderTop">
            <div>
              <p className="eyebrow">Latest visible event</p>
              <p className="detailKey">{latest.command}</p>
              <p className="detailMeta">
                {latest.session_key} · {latest.host} · {formatTimestamp(latest.timestamp_start)}
              </p>
            </div>
            <Link href={`/sessions/${encodeURIComponent(latest.session_key)}`} className="pill">
              Open session
            </Link>
          </div>

          <div className="pillRow">
            <span className="pill">{latest.actor_name || latest.actor_type}</span>
            <span className="pill">{latest.repository_name || latest.repository_root || "no repo"}</span>
            <span className="pill">{latest.shell}</span>
          </div>
        </section>
      ) : null}
    </DashboardShell>
  );
}
