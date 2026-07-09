import Link from "next/link";

import {
  DashboardShell,
  EmptyState,
  MiniStat,
} from "@/components/dashboard-shell";
import { CommandTranscript } from "@/components/command-transcript";
import { getSessionDetail } from "@/lib/api";
import { formatClock, formatDuration, formatTimestamp } from "@/lib/format";

export const dynamic = "force-dynamic";

function summarizeRepositories(commands: Awaited<ReturnType<typeof getSessionDetail>>["commands"]) {
  return [...new Set(commands.map((command) => command.repository_name || command.repository_root).filter(Boolean))];
}

export default async function SessionDetailPage(props: {
  params: Promise<{ sessionKey: string }>;
}) {
  const params = await props.params;
  const { session, commands, errors } = await getSessionDetail(params.sessionKey);

  if (!session && commands.length === 0) {
    return (
      <DashboardShell
        active="sessions"
        eyebrow="Session detail"
        title={params.sessionKey}
        description="No session data was found for this key."
        aside={<MiniStat label="Status" value="missing" />}
      >
        <EmptyState
          title="Session not found"
          detail="The session may not have been recorded yet, or the API may not have any command data for this key."
        />
      </DashboardShell>
    );
  }

  const orderedCommands = [...commands].reverse();
  const repositoryNames = summarizeRepositories(commands);
  const commandsCount = session?.commands_count ?? commands.length;
  const workedMs = session?.worked_ms ?? commands.reduce((sum, command) => sum + command.duration_ms, 0);
  const repositoriesCount = session?.repositories_count ?? repositoryNames.length;
  const actorCount = session?.actor_count ?? new Set(commands.map((command) => command.actor_name).filter(Boolean)).size;
  const failedCommands = commands.filter((command) => command.exit_code !== 0).length;

  return (
    <DashboardShell
      active="sessions"
      eyebrow="Session detail"
      title={session?.session_key ?? params.sessionKey}
      description={
        session
          ? `${session.host} · ${session.shell} · started ${formatTimestamp(session.started_at)}`
          : "Reconstructed from the timeline endpoint."
      }
      aside={
        <div className="statusGrid">
          <MiniStat label="Commands" value={commandsCount} />
          <MiniStat label="Worked time" value={formatDuration(workedMs)} />
          <MiniStat label="Repositories" value={repositoriesCount} />
        </div>
      }
    >
      {errors.length > 0 ? (
        <section className="card errorCard">
          <p className="errorTitle">Partial data loaded</p>
          <p className="errorDetail">{errors.join(" | ")}</p>
        </section>
      ) : null}

      <section className="card cardStrong detailHeaderCard">
        <div className="detailHeaderTop">
          <div>
            <p className="eyebrow">Reconstruction summary</p>
            <p className="detailKey">{session?.session_key ?? params.sessionKey}</p>
            <p className="detailMeta">
              {session ? (
                <>
                  {session.host} · {session.shell} · last seen {formatTimestamp(session.last_seen_at)}
                </>
              ) : (
                "Timeline-only reconstruction"
              )}
            </p>
          </div>

          <Link href="/sessions" className="pill">
            Back to sessions
          </Link>
        </div>

        <div className="pillRow">
          <span className="pill">{commandsCount} commands</span>
          <span className="pill">{formatDuration(workedMs)} worked</span>
          <span className="pill">{repositoriesCount} repositories</span>
          <span className="pill">{actorCount} actors</span>
          <span className="pill">{failedCommands} failed</span>
        </div>

        {session ? (
          <p className="detailMeta">
            {session.session_type} session started {formatTimestamp(session.started_at)} and was last
            seen {formatTimestamp(session.last_seen_at)}.
          </p>
        ) : null}
      </section>

      <section className="detailGrid">
        <div className="sectionHeader">
          <div>
            <h2 className="sectionTitle">Command trail</h2>
            <p className="sectionDetail">
              Ordered from first to last. Failures are highlighted so you can spot the debugging
              path.
            </p>
          </div>
        </div>

        <div className="commandList">
          {orderedCommands.length > 0 ? (
            orderedCommands.map((command, index) => {
              const redactedCount = command.redaction_findings.length;
              return (
                <article
                  key={command.id}
                  className="card commandItem"
                  data-exit={String(command.exit_code)}
                >
                  <div className="commandTop">
                    <div>
                      <p className="commandIndex">Step {index + 1}</p>
                      <p className="commandText">{command.command}</p>
                    </div>
                    <div className="commandExit">exit {command.exit_code}</div>
                  </div>

                  <div className="commandMetaRow">
                    <span className="pill">{formatClock(command.timestamp_start)}</span>
                    <span className="pill">{formatDuration(command.duration_ms)}</span>
                    <span className="pill">{command.shell}</span>
                    <span className="pill">{command.cwd}</span>
                    {command.repository_name ? <span className="pill">{command.repository_name}</span> : null}
                    {command.actor_name ? <span className="pill">{command.actor_name}</span> : null}
                    {redactedCount > 0 ? (
                      <span className="pill">{redactedCount} redactions</span>
                    ) : null}
                  </div>

                  <CommandTranscript
                    title="Transcript"
                    stdout={command.stdout}
                    stderr={command.stderr}
                    note={<span>Recorded for the session trail.</span>}
                  />
                </article>
              );
            })
          ) : (
            <EmptyState
              title="No commands attached to this session"
              detail="The session aggregate exists, but the timeline endpoint returned no command rows yet."
            />
          )}
        </div>
      </section>
    </DashboardShell>
  );
}
