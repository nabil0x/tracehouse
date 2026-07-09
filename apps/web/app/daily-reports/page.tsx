import Link from "next/link";

import {
  DashboardShell,
  EmptyState,
  MiniStat,
  SectionHeader,
  SessionMetric,
} from "@/components/dashboard-shell";
import { getDailySummaries, type DailySummaryRecord } from "@/lib/api";
import { formatCount, formatDate, formatDuration, formatTimestamp } from "@/lib/format";

export const dynamic = "force-dynamic";

type ChipLink = {
  label: string;
  href?: string;
};

function normalizeEntries(entries: unknown[]): ChipLink[] {
  return entries
    .map((entry) => {
      if (typeof entry === "string") {
        return { label: entry, href: entry.trim() ? `/timeline?repository=${encodeURIComponent(entry)}` : undefined };
      }
      if (entry && typeof entry === "object") {
        const record = entry as Record<string, unknown>;
        const label =
          (typeof record.label === "string" && record.label) ||
          (typeof record.name === "string" && record.name) ||
          (typeof record.value === "string" && record.value) ||
          (typeof record.tool === "string" && record.tool) ||
          (typeof record.repository === "string" && record.repository) ||
          (typeof record.path === "string" && record.path) ||
          "";
        const hrefSource =
          (typeof record.href === "string" && record.href) ||
          (typeof record.repository === "string" && record.repository) ||
          (typeof record.path === "string" && record.path) ||
          undefined;
        return {
          label,
          href: hrefSource ? `/timeline?repository=${encodeURIComponent(hrefSource)}` : undefined,
        };
      }
      return { label: String(entry), href: undefined };
    })
    .filter((entry) => entry.label.trim().length > 0);
}

function uniqueLabels(summaries: DailySummaryRecord[], select: (summary: DailySummaryRecord) => string) {
  return new Set(summaries.map(select).filter(Boolean)).size;
}

function DailySummaryCard({ summary, featured = false }: { summary: DailySummaryRecord; featured?: boolean }) {
  const repositories = normalizeEntries(summary.repositories);
  const tools = normalizeEntries(summary.top_tools);

  return (
    <article className={`card ${featured ? "cardStrong" : ""} detailHeaderCard`}>
      <div className="detailHeaderTop">
        <div>
          <p className="eyebrow">{formatDate(summary.summary_date)}</p>
          <p className="detailKey">{summary.summary_text}</p>
          <p className="detailMeta">
            {summary.host} · {formatDuration(summary.worked_ms)} worked · {formatCount(summary.commands_count)} commands ·{" "}
            {formatCount(summary.commits_count)} commits
          </p>
        </div>
        <Link href="/timeline" className="pill">
          Open timeline
        </Link>
      </div>

      {summary.mistake_text ? (
        <section className="summaryMistake">
          <p className="summaryMistakeLabel">Most expensive mistake</p>
          <p className="summaryMistakeText">{summary.mistake_text}</p>
        </section>
      ) : null}

      <div className="summaryColumns">
        <div>
          <p className="summaryColumnLabel">Top tools</p>
          <div className="pillRow">
            {tools.length > 0 ? (
              tools.map((tool) => (
                <span key={tool.label} className="pill">
                  {tool.label}
                </span>
              ))
            ) : (
              <span className="summaryEmpty">No tools captured yet.</span>
            )}
          </div>
        </div>

        <div>
          <p className="summaryColumnLabel">Repositories</p>
          <div className="pillRow">
            {repositories.length > 0 ? (
              repositories.map((repo) =>
                repo.href ? (
                  <Link key={repo.label} href={repo.href} className="pill">
                    {repo.label}
                  </Link>
                ) : (
                  <span key={repo.label} className="pill">
                    {repo.label}
                  </span>
                ),
              )
            ) : (
              <span className="summaryEmpty">No repository data yet.</span>
            )}
          </div>
        </div>
      </div>

      <p className="summaryCreated">Generated {formatTimestamp(summary.created_at)}</p>
    </article>
  );
}

export default async function DailyReportsPage() {
  const { items: summaries, error } = await getDailySummaries(60);
  const latest = summaries[0];
  const totalWorkedMs = summaries.reduce((sum, summary) => sum + summary.worked_ms, 0);
  const totalCommands = summaries.reduce((sum, summary) => sum + summary.commands_count, 0);
  const totalCommits = summaries.reduce((sum, summary) => sum + summary.commits_count, 0);
  const hosts = uniqueLabels(summaries, (summary) => summary.host);

  return (
    <DashboardShell
      active="dailyReports"
      eyebrow="Daily Reports"
      title="Read the workday back as a written log."
      description="Daily summaries combine command volume, git movement, and the most expensive mistake into a narrative you can scan in seconds."
      aside={
        <div className="statusGrid">
          <MiniStat label="Reports" value={formatCount(summaries.length)} />
          <MiniStat label="Worked time" value={formatDuration(totalWorkedMs)} />
          <MiniStat label="Commands" value={formatCount(totalCommands)} />
          <MiniStat label="Commits" value={formatCount(totalCommits)} />
        </div>
      }
    >
      {error ? (
        <section className="card errorCard">
          <p className="errorTitle">Daily reports are partially unavailable</p>
          <p className="errorDetail">{error}</p>
        </section>
      ) : null}

      <section className="metricGrid">
        <SessionMetric
          label="Reports"
          value={formatCount(summaries.length)}
          detail="daily summaries loaded from the local API"
        />
        <SessionMetric
          label="Hosts"
          value={formatCount(hosts)}
          detail="machines that contributed workday summaries"
        />
        <SessionMetric
          label="Average commands"
          value={summaries.length > 0 ? formatCount(Math.round(totalCommands / summaries.length)) : "0"}
          detail="per daily report in the current sample"
        />
        <SessionMetric
          label="Average worked time"
          value={summaries.length > 0 ? formatDuration(Math.round(totalWorkedMs / summaries.length)) : "0 ms"}
          detail="per daily report in the current sample"
        />
      </section>

      <SectionHeader
        title="Daily work journal"
        detail="The latest report appears first. Each card contains the evidence that built the summary."
      />

      <div className="dailyReportList">
        {summaries.length > 0 ? (
          summaries.map((summary, index) => (
            <DailySummaryCard key={summary.id} summary={summary} featured={index === 0} />
          ))
        ) : (
          <EmptyState
            title="No daily reports yet"
            detail="Once the collector has enough data, the system will begin generating end-of-day summaries here."
          />
        )}
      </div>

      {latest ? (
        <section className="card detailHeaderCard">
          <div className="detailHeaderTop">
            <div>
              <p className="eyebrow">Latest report</p>
              <p className="detailKey">{formatDate(latest.summary_date)}</p>
              <p className="detailMeta">
                {latest.host} · generated {formatTimestamp(latest.created_at)}
              </p>
            </div>
            <Link href="/timeline" className="pill">
              Browse timeline
            </Link>
          </div>

          <div className="pillRow">
            <span className="pill">{formatDuration(latest.worked_ms)} worked</span>
            <span className="pill">{formatCount(latest.commands_count)} commands</span>
            <span className="pill">{formatCount(latest.commits_count)} commits</span>
          </div>
        </section>
      ) : null}
    </DashboardShell>
  );
}
