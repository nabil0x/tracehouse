import Link from "next/link";

import {
  DashboardShell,
  EmptyState,
  MiniStat,
  SectionHeader,
  SessionMetric,
} from "@/components/dashboard-shell";
import { getAgents, type AgentRecord } from "@/lib/api";
import { formatCount, formatTimestamp } from "@/lib/format";

export const dynamic = "force-dynamic";

function uniqueCount(agents: AgentRecord[], select: (agent: AgentRecord) => string | null) {
  return new Set(agents.map(select).filter(Boolean)).size;
}

function metadataCount(metadata: Record<string, unknown>): number {
  return Object.keys(metadata).length;
}

export default async function AgentsPage() {
  const { items: agents, error } = await getAgents(100);
  const latest = agents[0];
  const hosts = uniqueCount(agents, (agent) => agent.host);
  const agentTypeCount = agents.filter((agent) => agent.actor_type === "agent").length;
  const humanTypeCount = agents.filter((agent) => agent.actor_type === "human").length;
  const linkedSessions = uniqueCount(agents, (agent) => agent.agent_session_id || null);
  const metadataFields = agents.reduce((sum, agent) => sum + metadataCount(agent.metadata), 0);

  return (
    <DashboardShell
      active="agents"
      eyebrow="Agents"
      title="Track human and AI actors side by side."
      description="See which agents show up in the ledger, when they were last seen, and how they map back to the command timeline."
      aside={
        <div className="statusGrid">
          <MiniStat label="Agent rows" value={formatCount(agents.length)} />
          <MiniStat label="Hosts" value={formatCount(hosts)} />
          <MiniStat label="AI actors" value={formatCount(agentTypeCount)} />
          <MiniStat label="Linked sessions" value={formatCount(linkedSessions)} />
        </div>
      }
    >
      {error ? (
        <section className="card errorCard">
          <p className="errorTitle">Agent data is unavailable</p>
          <p className="errorDetail">{error}</p>
        </section>
      ) : null}

      <section className="metricGrid">
        <SessionMetric
          label="Agent rows"
          value={formatCount(agents.length)}
          detail="actor records loaded from the local API"
        />
        <SessionMetric
          label="AI actors"
          value={formatCount(agentTypeCount)}
          detail="actors tagged as automation or agent activity"
        />
        <SessionMetric
          label="Human actors"
          value={formatCount(humanTypeCount)}
          detail="rows that represent direct human activity"
        />
        <SessionMetric
          label="Metadata fields"
          value={formatCount(metadataFields)}
          detail="auxiliary actor data available for enrichment"
        />
      </section>

      <SectionHeader
        title="Agent index"
        detail="Each agent card links into the timeline filtered to that actor."
        action={
          <Link href="/timeline" className="subtleLink">
            Browse commands
          </Link>
        }
      />

      <div className="detailGrid">
        {agents.length > 0 ? (
          agents.map((agent) => {
            const metadataFieldsCount = metadataCount(agent.metadata);
            return (
              <article key={agent.id} className="card cardStrong detailHeaderCard">
                <div className="detailHeaderTop">
                  <div>
                    <p className="eyebrow">{agent.actor_type}</p>
                    <p className="detailKey">{agent.actor_name}</p>
                    <p className="detailMeta">
                      {agent.host} · {agent.agent_session_id || "no agent session id"}
                    </p>
                  </div>
                  <Link
                    href={`/timeline?actor_name=${encodeURIComponent(agent.actor_name)}&actor_type=${encodeURIComponent(agent.actor_type)}`}
                    className="pill"
                  >
                    Open timeline
                  </Link>
                </div>

                <div className="pillRow">
                  <span className="pill">host {agent.host}</span>
                  <span className="pill">first seen {formatTimestamp(agent.first_seen_at)}</span>
                  <span className="pill">last seen {formatTimestamp(agent.last_seen_at)}</span>
                  {agent.agent_session_id ? (
                    <span className="pill">session {agent.agent_session_id}</span>
                  ) : null}
                  {metadataFieldsCount > 0 ? (
                    <span className="pill">{metadataFieldsCount} metadata fields</span>
                  ) : null}
                </div>
              </article>
            );
          })
        ) : (
          <EmptyState
            title="No agents indexed yet"
            detail="As commands are captured, the collector will surface human and AI actors here."
          />
        )}
      </div>

      {latest ? (
        <section className="card detailHeaderCard">
          <div className="detailHeaderTop">
            <div>
              <p className="eyebrow">Most recent actor</p>
              <p className="detailKey">{latest.actor_name}</p>
              <p className="detailMeta">
                {latest.host} · last seen {formatTimestamp(latest.last_seen_at)}
              </p>
            </div>
            <Link
              href={`/timeline?actor_name=${encodeURIComponent(latest.actor_name)}&actor_type=${encodeURIComponent(latest.actor_type)}`}
              className="pill"
            >
              View commands
            </Link>
          </div>

          <div className="pillRow">
            <span className="pill">{latest.actor_type}</span>
            <span className="pill">{latest.agent_session_id || "no agent session"}</span>
          </div>
        </section>
      ) : null}
    </DashboardShell>
  );
}
