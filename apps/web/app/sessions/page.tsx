import Link from "next/link";

import {
  DashboardShell,
  EmptyState,
  MiniStat,
  SectionHeader,
} from "@/components/dashboard-shell";
import { SessionRow } from "@/components/session-row";
import { getSessionList, type SessionSummary } from "@/lib/api";
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

export default async function SessionsPage() {
  const { items: sessions, total, error } = await getSessionList(100);
  const totals = summarizeSessions(sessions);
  const latest = sessions[0];

  return (
    <DashboardShell
      active="sessions"
      eyebrow="Sessions"
      title="Every work session, reconstructed from evidence."
      description="Browse full terminal sessions, then open one to see the ordered command trail and the context around failures."
      aside={
        <div className="statusGrid">
          <MiniStat label="Sessions indexed" value={formatCount(total)} />
          <MiniStat label="Commands captured" value={formatCount(totals.commands)} />
          <MiniStat label="Worked time" value={formatDuration(totals.workedMs)} />
        </div>
      }
    >
      {error ? (
        <section className="card errorCard">
          <p className="errorTitle">Unable to load sessions</p>
          <p className="errorDetail">{error}</p>
        </section>
      ) : null}

      <SectionHeader
        title="Session index"
        detail="The newest sessions appear first. Open one to inspect the full command sequence."
        action={
          latest ? (
            <Link href={`/sessions/${encodeURIComponent(latest.session_key)}`} className="subtleLink">
              Open latest session
            </Link>
          ) : null
        }
      />

      <div className="sessionList">
        {sessions.length > 0 ? (
          sessions.map((session) => <SessionRow key={session.id} session={session} />)
        ) : (
          <EmptyState
            title="No sessions indexed yet"
            detail="Once the collector records commands, each shell session will appear here with its aggregate metrics."
          />
        )}
      </div>

      {latest ? (
        <section className="card detailHeaderCard">
          <div className="detailHeaderTop">
            <div>
              <p className="eyebrow">Latest session summary</p>
              <p className="detailKey">{latest.session_key}</p>
              <p className="detailMeta">
                {latest.host} · {latest.shell} · started {formatTimestamp(latest.started_at)}
              </p>
            </div>
            <Link
              href={`/sessions/${encodeURIComponent(latest.session_key)}`}
              className="pill"
            >
              View reconstruction
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
