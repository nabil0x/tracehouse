import Link from "next/link";

import { formatDuration, formatTimestamp } from "@/lib/format";
import type { SessionSummary } from "@/lib/api";

type SessionRowProps = {
  session: SessionSummary;
};

export function SessionRow({ session }: SessionRowProps) {
  return (
    <Link href={`/sessions/${encodeURIComponent(session.session_key)}`} className="sessionRow">
      <div>
        <p className="sessionKey">{session.session_key}</p>
        <p className="sessionMeta">
          {session.host} · {session.shell} · last seen {formatTimestamp(session.last_seen_at)}
        </p>
      </div>
      <div className="sessionMetric">
        <span className="sessionMetricLabel">Commands</span>
        <span className="sessionMetricValue">{session.commands_count}</span>
      </div>
      <div className="sessionMetric">
        <span className="sessionMetricLabel">Worked</span>
        <span className="sessionMetricValue">{formatDuration(session.worked_ms)}</span>
      </div>
      <div className="sessionMetric">
        <span className="sessionMetricLabel">Repos</span>
        <span className="sessionMetricValue">{session.repositories_count}</span>
      </div>
      <div className="sessionMetric">
        <span className="sessionMetricLabel">Actors</span>
        <span className="sessionMetricValue">{session.actor_count}</span>
      </div>
      <div className="sessionArrow" aria-hidden="true">
        →
      </div>
    </Link>
  );
}
