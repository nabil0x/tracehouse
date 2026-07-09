import Link from "next/link";

import {
  DashboardShell,
  EmptyState,
  MiniStat,
  SectionHeader,
  SessionMetric,
} from "@/components/dashboard-shell";
import { getCommits, getTimeline, type CommitRecord, type CommandRecord } from "@/lib/api";
import { formatCount, formatDate, formatDuration, formatTimestamp } from "@/lib/format";

export const dynamic = "force-dynamic";

type CountEntry = {
  label: string;
  value: number;
  detail?: string;
  href?: string;
};

const WEEKDAY_LABELS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
const HOUR_LABELS = Array.from({ length: 24 }, (_, index) => String(index).padStart(2, "0"));

function countBy<T>(items: T[], select: (item: T) => string | null | undefined): CountEntry[] {
  const counts = new Map<string, number>();
  for (const item of items) {
    const label = select(item)?.trim();
    if (!label) {
      continue;
    }
    counts.set(label, (counts.get(label) ?? 0) + 1);
  }

  return [...counts.entries()]
    .map(([label, value]) => ({ label, value }))
    .sort((left, right) => right.value - left.value || left.label.localeCompare(right.label));
}

function commandLabel(command: CommandRecord): string {
  return command.actor_name || command.actor_type || "unknown actor";
}

function repositoryLabel(command: CommandRecord): string {
  return command.repository_name || command.repository_root || "no repository";
}

function failureSignature(command: CommandRecord): string {
  const source = command.stderr || command.stdout;
  if (!source) {
    return `exit ${command.exit_code}`;
  }
  const firstLine = source
    .split("\n")
    .map((line) => line.trim())
    .find(Boolean);
  if (!firstLine) {
    return `exit ${command.exit_code}`;
  }
  return firstLine.length > 90 ? `${firstLine.slice(0, 90).trimEnd()}...` : firstLine;
}

function normalizeCountEntries(entries: CountEntry[], limit = 6): CountEntry[] {
  return entries.slice(0, limit);
}

function sumDuration(commands: CommandRecord[]): number {
  return commands.reduce((total, command) => total + command.duration_ms, 0);
}

function buildHeatmap(commands: CommandRecord[]) {
  const matrix = Array.from({ length: 7 }, () => Array.from({ length: 24 }, () => 0));
  for (const command of commands) {
    const timestamp = new Date(command.timestamp_start);
    if (Number.isNaN(timestamp.getTime())) {
      continue;
    }
    matrix[timestamp.getUTCDay()][timestamp.getUTCHours()] += 1;
  }
  const peak = Math.max(...matrix.flat(), 1);
  return { matrix, peak };
}

function chartWidth(value: number, peak: number): string {
  const ratio = peak > 0 ? value / peak : 0;
  return `${Math.max(ratio * 100, value > 0 ? 6 : 0)}%`;
}

function BarChartSection({
  title,
  detail,
  items,
  emptyTitle,
  emptyDetail,
}: {
  title: string;
  detail: string;
  items: CountEntry[];
  emptyTitle: string;
  emptyDetail: string;
}) {
  const peak = Math.max(...items.map((item) => item.value), 1);

  return (
    <section className="card chartCard">
      <SectionHeader title={title} detail={detail} />
      {items.length > 0 ? (
        <div className="chartList">
          {items.map((item) => (
            <div key={item.label} className="chartRow">
              <div className="chartRowTop">
                <div>
                  <p className="chartRowLabel">{item.label}</p>
                  {item.detail ? <p className="chartRowDetail">{item.detail}</p> : null}
                </div>
                <span className="chartRowValue">{formatCount(item.value)}</span>
              </div>
              <div className="chartTrack" aria-hidden="true">
                <div className="chartFill" style={{ width: chartWidth(item.value, peak) }} />
              </div>
            </div>
          ))}
        </div>
      ) : (
        <EmptyState title={emptyTitle} detail={emptyDetail} />
      )}
    </section>
  );
}

function HeatmapSection({
  commands,
}: {
  commands: CommandRecord[];
}) {
  const { matrix, peak } = buildHeatmap(commands);

  return (
    <section className="card chartCard heatmapCard">
      <SectionHeader
        title="Command heatmap"
        detail="Command density by UTC day and hour. Darker cells mean more terminal activity."
      />
      {commands.length > 0 ? (
        <div className="heatmapGrid" role="img" aria-label="Command heatmap by weekday and hour">
          <div className="heatmapHeader">
            <span className="heatmapCorner" />
            {HOUR_LABELS.map((hour) => (
              <span key={hour} className="heatmapHourLabel">
                {hour}
              </span>
            ))}
          </div>
          {WEEKDAY_LABELS.map((dayLabel, dayIndex) => (
            <div key={dayLabel} className="heatmapRow">
              <span className="heatmapDayLabel">{dayLabel}</span>
              {matrix[dayIndex].map((count, hourIndex) => {
                const intensity = count / peak;
                return (
                  <span
                    key={`${dayLabel}-${hourIndex}`}
                    className="heatmapCell"
                    title={`${dayLabel} ${HOUR_LABELS[hourIndex]}:00 UTC · ${count} commands`}
                    style={{
                      backgroundColor: `rgba(125, 211, 252, ${0.06 + intensity * 0.84})`,
                      borderColor: `rgba(125, 211, 252, ${0.08 + intensity * 0.38})`,
                    }}
                  />
                );
              })}
            </div>
          ))}
        </div>
      ) : (
        <EmptyState
          title="No activity yet"
          detail="As commands are captured, the heatmap will show the hours and days that matter most."
        />
      )}
    </section>
  );
}

function CommitActivity({ commits }: { commits: CommitRecord[] }) {
  const byRepository = normalizeCountEntries(countBy(commits, (commit) => commit.repository_name || commit.repository_root));
  const byDay = [...new Map(commits.map((commit) => [commit.committed_at.slice(0, 10), 0] as const)).keys()]
    .map((day) => {
      const value = commits.filter((commit) => commit.committed_at.slice(0, 10) === day).length;
      return {
        label: formatDate(day),
        value,
        detail: day,
      };
    })
    .sort((left, right) => right.detail!.localeCompare(left.detail!))
    .slice(0, 8);

  return (
    <div className="chartGrid">
      <BarChartSection
        title="Git activity by repository"
        detail="Commit frequency shows which workspaces are producing the most git movement."
        items={byRepository}
        emptyTitle="No commit activity yet"
        emptyDetail="Once git commits are recorded, the repository graph will light up here."
      />
      <BarChartSection
        title="Git activity by day"
        detail="Recent commit cadence, grouped by the day they were authored."
        items={byDay}
        emptyTitle="No commit dates yet"
        emptyDetail="The chart will populate as commit events are captured."
      />
    </div>
  );
}

function formatActorDetail(commands: CommandRecord[], actorName: string): string {
  const actorCommands = commands.filter((command) => command.actor_name === actorName);
  const failures = actorCommands.filter((command) => command.exit_code !== 0).length;
  const successRate = actorCommands.length > 0 ? Math.round(((actorCommands.length - failures) / actorCommands.length) * 100) : 0;
  return `${actorCommands.length} commands · ${successRate}% success · ${formatDuration(sumDuration(actorCommands))}`;
}

export default async function AnalyticsPage() {
  const [timelineResult, commitsResult] = await Promise.all([
    getTimeline({ limit: 500 }),
    getCommits(200),
  ]);

  const commands = timelineResult.items;
  const commits = commitsResult.items;
  const totalCommands = timelineResult.total;
  const totalVisibleCommands = commands.length;
  const failedCommands = commands.filter((command) => command.exit_code !== 0);
  const agentCommands = commands.filter((command) => command.actor_type === "agent");
  const humanCommands = commands.filter((command) => command.actor_type === "human");
  const workMs = sumDuration(commands);
  const repoCount = new Set(commands.map((command) => repositoryLabel(command)).filter((label) => label !== "no repository")).size;
  const shellEntries = normalizeCountEntries(countBy(commands, (command) => command.shell), 5);
  const repositoryEntries = normalizeCountEntries(
    countBy(commands, repositoryLabel).filter((entry) => entry.label !== "no repository"),
    6,
  );
  const actorEntries = normalizeCountEntries(countBy(commands, commandLabel), 6).map((entry) => ({
    ...entry,
    detail: formatActorDetail(commands, entry.label),
  }));
  const failureEntries = normalizeCountEntries(
    countBy(failedCommands, failureSignature).map((entry) => ({
      ...entry,
      detail: `${entry.value} occurrences`,
    })),
    6,
  );
  const exitCodeEntries = normalizeCountEntries(
    countBy(failedCommands, (command) => `exit ${command.exit_code}`),
    6,
  );
  const latestCommand = commands[0];
  const latestCommit = commits[0];

  return (
    <DashboardShell
      active="analytics"
      eyebrow="Analytics"
      title="Turn the command trail into operational signal."
      description="These views are derived from the latest command, git, and summary evidence so you can spot patterns without leaving the local ledger."
      aside={
        <div className="statusGrid">
          <MiniStat label="Indexed commands" value={formatCount(totalCommands)} />
          <MiniStat label="Sampled commands" value={formatCount(totalVisibleCommands)} />
          <MiniStat label="Commit events" value={formatCount(commits.length)} />
          <MiniStat label="Active repos" value={formatCount(repoCount)} />
        </div>
      }
    >
      {timelineResult.error || commitsResult.error ? (
        <section className="card errorCard">
          <p className="errorTitle">Analytics data is partially unavailable</p>
          <p className="errorDetail">
            {[timelineResult.error, commitsResult.error].filter(Boolean).join(" | ")}
          </p>
        </section>
      ) : null}

      <section className="metricGrid">
        <SessionMetric
          label="Command success rate"
          value={`${Math.round(((commands.length - failedCommands.length) / Math.max(commands.length, 1)) * 100)}%`}
          detail="measured from the sampled timeline rows"
        />
        <SessionMetric
          label="Agent share"
          value={`${Math.round((agentCommands.length / Math.max(commands.length, 1)) * 100)}%`}
          detail="commands attributed to AI agents"
        />
        <SessionMetric
          label="Human share"
          value={`${Math.round((humanCommands.length / Math.max(commands.length, 1)) * 100)}%`}
          detail="commands attributed to direct human activity"
        />
        <SessionMetric
          label="Worked time"
          value={formatDuration(workMs)}
          detail="aggregated across the sampled command trail"
        />
      </section>

      <section className="chartGrid">
        <HeatmapSection commands={commands} />
        <BarChartSection
          title="Exit code distribution"
          detail="How often the sampled command trail ended in failure."
          items={exitCodeEntries}
          emptyTitle="No failures recorded"
          emptyDetail="When commands start failing, the exit code chart will show the distribution here."
        />
      </section>

      <SectionHeader
        title="Command and agent comparison"
        detail="Compare the most active shells, repositories, and actors side by side."
      />

      <div className="chartGrid">
        <BarChartSection
          title="Top shells"
          detail="Which shells appear most often in the sampled ledger."
          items={shellEntries}
          emptyTitle="No shell data yet"
          emptyDetail="Shell usage will appear here once the collector records a few commands."
        />
        <BarChartSection
          title="Top repositories"
          detail="Repositories with the most command activity in the latest sample."
          items={repositoryEntries}
          emptyTitle="No repository data yet"
          emptyDetail="Repository activity will populate once commands run inside a workspace."
        />
        <BarChartSection
          title="Top actors"
          detail="People and agents sorted by command count."
          items={actorEntries}
          emptyTitle="No actor data yet"
          emptyDetail="Actor comparisons will appear once human and AI activity is captured."
        />
      </div>

      <SectionHeader
        title="Error focus"
        detail="The failure signatures below surface repeated debugging patterns before you have to search for them."
      />

      <div className="chartGrid">
        <BarChartSection
          title="Failure signatures"
          detail="Grouped by the first meaningful stderr or stdout line."
          items={failureEntries}
          emptyTitle="No error signatures yet"
          emptyDetail="Once failing commands are captured, recurring error text will be grouped here."
        />
        <BarChartSection
          title="Agent effectiveness"
          detail="Highest-volume agent actors and their aggregate success rates."
          items={normalizeCountEntries(
            countBy(agentCommands, (command) => command.actor_name || command.agent_session_id || "unknown agent").map(
              (entry) => ({
                ...entry,
                detail: formatActorDetail(agentCommands, entry.label),
              }),
            ),
            5,
          )}
          emptyTitle="No agent data yet"
          emptyDetail="AI actor comparisons will appear once the collector sees agent-driven work."
        />
      </div>

      <SectionHeader
        title="Git activity"
        detail="Commit cadence and repository movement give you the historical context around terminal work."
        action={
          <Link href="/repositories" className="subtleLink">
            Open repositories
          </Link>
        }
      />

      <CommitActivity commits={commits} />

      {latestCommand ? (
        <section className="card cardStrong detailHeaderCard">
          <div className="detailHeaderTop">
            <div>
              <p className="eyebrow">Latest command in sample</p>
              <p className="detailKey">{latestCommand.command}</p>
              <p className="detailMeta">
                {latestCommand.host} · {latestCommand.shell} · {formatTimestamp(latestCommand.timestamp_start)}
              </p>
            </div>
            <Link href="/timeline" className="pill">
              Open timeline
            </Link>
          </div>

          <div className="pillRow">
            <span className="pill">{latestCommand.actor_name || latestCommand.actor_type}</span>
            <span className="pill">{repositoryLabel(latestCommand)}</span>
            <span className="pill">exit {latestCommand.exit_code}</span>
            <span className="pill">{formatDuration(latestCommand.duration_ms)}</span>
          </div>
        </section>
      ) : null}

      {latestCommit ? (
        <section className="card detailHeaderCard">
          <div className="detailHeaderTop">
            <div>
              <p className="eyebrow">Latest commit</p>
              <p className="detailKey">{latestCommit.message}</p>
              <p className="detailMeta">
                {latestCommit.repository_name || latestCommit.repository_root || "unknown repo"} ·{" "}
                {formatTimestamp(latestCommit.committed_at)}
              </p>
            </div>
            <Link
              href={
                latestCommit.commit_hash
                  ? `/commits/${encodeURIComponent(latestCommit.commit_hash)}${latestCommit.repository_name || latestCommit.repository_root ? `?repository=${encodeURIComponent(latestCommit.repository_name || latestCommit.repository_root || "")}` : ""}`
                  : `/timeline?repository=${encodeURIComponent(
                      latestCommit.repository_name || latestCommit.repository_root || "",
                    )}`
              }
              className="pill"
            >
              Open commit
            </Link>
          </div>

          <div className="pillRow">
            <span className="pill">{latestCommit.author_name || "unknown author"}</span>
            <span className="pill">{latestCommit.commit_hash.slice(0, 12)}</span>
            {latestCommit.diff_summary ? <span className="pill">{latestCommit.diff_summary}</span> : null}
          </div>
        </section>
      ) : null}
    </DashboardShell>
  );
}
