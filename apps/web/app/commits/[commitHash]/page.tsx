import Link from "next/link";

import {
  DashboardShell,
  EmptyState,
  MiniStat,
  SectionHeader,
  SessionMetric,
} from "@/components/dashboard-shell";
import { CommandTranscript } from "@/components/command-transcript";
import { getCommitDetail, type CommandRecord, type FileChangeRecord } from "@/lib/api";
import { formatCount, formatDuration, formatClock, formatTimestamp } from "@/lib/format";

export const dynamic = "force-dynamic";

type SearchParams = Record<string, string | string[] | undefined>;

function firstSearchParam(value: string | string[] | undefined): string | undefined {
  if (Array.isArray(value)) {
    return value[0];
  }
  return value;
}

function FileChangeCard({ change }: { change: FileChangeRecord }) {
  const pathLabel = change.old_path && change.old_path !== change.path ? `${change.old_path} → ${change.path}` : change.path;

  return (
    <article className="card settingsPanel">
      <div className="detailHeaderTop">
        <div>
          <p className="eyebrow">{change.change_type}</p>
          <p className="detailKey">{pathLabel}</p>
          <p className="detailMeta">
            {change.repository_name || change.repository_root || "unknown repo"} · {change.commit_hash?.slice(0, 12) || "unknown commit"}
          </p>
        </div>
      </div>

      <div className="pillRow">
        <span className="pill">+{change.lines_added}</span>
        <span className="pill">-{change.lines_removed}</span>
        {change.committed_at ? <span className="pill">{formatTimestamp(change.committed_at)}</span> : null}
      </div>
    </article>
  );
}

function RelatedCommandCard({ command }: { command: CommandRecord }) {
  return (
    <article className="card commandItem" data-exit={String(command.exit_code)}>
      <div className="commandTop">
        <div>
          <p className="commandIndex">{command.session_key}</p>
          <p className="commandText">{command.command}</p>
        </div>
        <div className="commandExit">exit {command.exit_code}</div>
      </div>

      <div className="commandMetaRow">
        <span className="pill">{formatClock(command.timestamp_start)}</span>
        <span className="pill">{formatDuration(command.duration_ms)}</span>
        <span className="pill">{command.shell}</span>
        <span className="pill">{command.actor_name || command.actor_type}</span>
        <span className="pill">{command.repository_name || command.repository_root || "no repository"}</span>
      </div>

      <CommandTranscript
        title="Transcript"
        stdout={command.stdout}
        stderr={command.stderr}
        note={<span>This command shares the same commit context.</span>}
      />
    </article>
  );
}

export default async function CommitDetailPage(props: {
  params: Promise<{ commitHash: string }>;
  searchParams: Promise<SearchParams>;
}) {
  const params = await props.params;
  const searchParams = await props.searchParams;
  const repository = firstSearchParam(searchParams.repository)?.trim() || undefined;
  const result = await getCommitDetail(params.commitHash, repository);
  const commit = result.commit;
  const fileChanges = result.file_changes;
  const relatedCommands = result.related_commands;
  const repositoryFilter = commit?.repository_name || commit?.repository_root || repository || undefined;
  const repositoryLabel = repositoryFilter || "unknown repository";
  const linesAdded = fileChanges.reduce((sum, change) => sum + change.lines_added, 0);
  const linesRemoved = fileChanges.reduce((sum, change) => sum + change.lines_removed, 0);
  const fileCount = new Set(fileChanges.map((change) => change.path)).size;
  const workedMs = relatedCommands.reduce((sum, command) => sum + command.duration_ms, 0);
  const failedCommands = relatedCommands.filter((command) => command.exit_code !== 0).length;

  return (
    <DashboardShell
      active="search"
      eyebrow="Commit detail"
      title={commit?.message || params.commitHash}
      description={
        commit
          ? `${repositoryLabel} · committed ${formatTimestamp(commit.committed_at)}`
          : "A commit drill-down reconstructed from the evidence in the local database."
      }
      aside={
        <div className="statusGrid">
          <MiniStat label="Files" value={formatCount(fileCount)} />
          <MiniStat label="Lines added" value={formatCount(linesAdded)} />
          <MiniStat label="Lines removed" value={formatCount(linesRemoved)} />
          <MiniStat label="Related commands" value={formatCount(relatedCommands.length)} />
        </div>
      }
    >
      {result.error ? (
        <section className="card errorCard">
          <p className="errorTitle">Commit data is unavailable</p>
          <p className="errorDetail">{result.error}</p>
        </section>
      ) : null}

      {result.errors.length > 0 ? (
        <section className="card errorCard">
          <p className="errorTitle">Partial reconstruction</p>
          <p className="errorDetail">{result.errors.join(" | ")}</p>
        </section>
      ) : null}

      {commit ? (
        <section className="card cardStrong detailHeaderCard">
          <div className="detailHeaderTop">
            <div>
              <p className="eyebrow">Commit summary</p>
              <p className="detailKey">{commit.message}</p>
              <p className="detailMeta">
                {repositoryLabel} · {commit.author_name || "unknown author"} · {commit.commit_hash}
              </p>
            </div>
            <Link
              href={`/timeline?git_commit_hash=${encodeURIComponent(commit.commit_hash)}${
                repositoryFilter ? `&repository=${encodeURIComponent(repositoryFilter)}` : ""
              }`}
              className="pill"
            >
              Open timeline
            </Link>
          </div>

          <div className="pillRow">
            <span className="pill">{commit.commit_hash.slice(0, 12)}</span>
            <span className="pill">{commit.author_name || "unknown author"}</span>
            <span className="pill">{formatTimestamp(commit.committed_at)}</span>
            {commit.diff_summary ? <span className="pill">{commit.diff_summary}</span> : null}
          </div>
        </section>
      ) : null}

      <section className="metricGrid">
        <SessionMetric
          label="Related commands"
          value={formatCount(relatedCommands.length)}
          detail="commands captured with the same git commit hash"
        />
        <SessionMetric
          label="Failed commands"
          value={formatCount(failedCommands)}
          detail="debugging effort associated with the commit"
        />
        <SessionMetric
          label="Worked time"
          value={formatDuration(workedMs)}
          detail="sum of related command durations"
        />
        <SessionMetric
          label="File changes"
          value={formatCount(fileCount)}
          detail="paths touched in the commit record"
        />
      </section>

      <SectionHeader
        title="File changes"
        detail="The file-change rows are stored separately from the commit, so they can be queried directly later."
      />

      <div className="settingsGrid">
        {fileChanges.length > 0 ? (
          fileChanges.map((change) => <FileChangeCard key={change.id} change={change} />)
        ) : (
          <EmptyState
            title="No file changes recorded yet"
            detail="The commit exists, but the file-change table has not been populated for this commit yet."
          />
        )}
      </div>

      <SectionHeader
        title="Related commands"
        detail="These commands share the same commit hash and provide the terminal trail around the change."
      />

      <div className="commandList">
        {relatedCommands.length > 0 ? (
          relatedCommands.map((command) => <RelatedCommandCard key={command.id} command={command} />)
        ) : (
          <EmptyState
            title="No related commands"
            detail="Commands will appear here once the collector records activity with the same git commit hash."
          />
        )}
      </div>
    </DashboardShell>
  );
}
