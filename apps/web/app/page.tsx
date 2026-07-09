import Link from "next/link";

import {
  DashboardShell,
  EmptyState,
  MiniStat,
  SectionHeader,
  SessionMetric,
} from "@/components/dashboard-shell";
import { SessionRow } from "@/components/session-row";
import { getSessions, type SessionSummary } from "@/lib/api";
import { formatCount, formatDuration, formatTimestamp } from "@/lib/format";

export const dynamic = "force-dynamic";

function summarizeSessions(sessions: SessionSummary[]) {
  return sessions.reduce(
    (acc, session) => ({
      commands: acc.commands + session.commands_count,
      workedMs: acc.workedMs + session.worked_ms,
      active: acc.active + (session.ended_at ? 0 : 1),
    }),
    { commands: 0, workedMs: 0, active: 0 },
  );
}

export default async function OverviewPage() {
  const { items: sessions, total, error } = await getSessions(8);
  const totals = summarizeSessions(sessions);
  const latest = sessions[0];
  const apiUrl = process.env.ABSOLUTELY_API_URL?.trim() || "http://127.0.0.1:18400";

  return (
    <DashboardShell
      active="overview"
      eyebrow="Overview"
      title="Reconstruct the session, not just the command."
      description="Tracehouse keeps shell activity, repository context, and agent identity in one local-first ledger."
      aside={
        <div className="statusGrid">
          <div className="statusPill">Connected to {apiUrl}</div>
          <MiniStat label="Recent sessions" value={formatCount(total)} />
          <MiniStat label="Preview commands" value={formatCount(totals.commands)} />
          <MiniStat label="Work in preview" value={formatDuration(totals.workedMs)} />
        </div>
      }
    >
      {error ? (
        <section className="card errorCard">
          <p className="errorTitle">Dashboard data is unavailable</p>
          <p className="errorDetail">{error}</p>
        </section>
      ) : null}

      <section className="metricGrid">
        <SessionMetric
          label="Recent sessions"
          value={formatCount(total)}
          detail="loaded from the local API"
        />
        <SessionMetric
          label="Commands captured"
          value={formatCount(totals.commands)}
          detail="across the visible session preview"
        />
        <SessionMetric
          label="Worked time"
          value={formatDuration(totals.workedMs)}
          detail="aggregated from session summaries"
        />
        <SessionMetric
          label="Active sessions"
          value={formatCount(totals.active)}
          detail="sessions without an end marker"
        />
      </section>

      <SectionHeader
        title="Recent sessions"
        detail="Open a session to reconstruct the full command sequence."
        action={
          <Link href="/sessions" className="subtleLink">
            View full index
          </Link>
        }
      />

      <div className="sessionList">
        {sessions.length > 0 ? (
          sessions.map((session) => <SessionRow key={session.id} session={session} />)
        ) : (
          <EmptyState
            title="No sessions yet"
            detail="Start the collector, run a few commands, and this dashboard will begin to reconstruct the work."
          />
        )}
      </div>

      {latest ? (
        <section className="card cardStrong detailHeaderCard">
          <div className="detailHeaderTop">
            <div>
              <p className="eyebrow">Most recent session</p>
              <p className="detailKey">{latest.session_key}</p>
              <p className="detailMeta">
                {latest.host} · {latest.shell} · last seen {formatTimestamp(latest.last_seen_at)}
              </p>
            </div>
            <Link
              href={`/sessions/${encodeURIComponent(latest.session_key)}`}
              className="pill"
            >
              Open session detail
            </Link>
          </div>

          <div className="pillRow">
            <span className="pill">{latest.commands_count} commands</span>
            <span className="pill">{formatDuration(latest.worked_ms)} worked</span>
            <span className="pill">{latest.repositories_count} repositories</span>
            <span className="pill">{latest.actor_count} actors</span>
          </div>
        </section>
      ) : null}
    </DashboardShell>
  );
}
