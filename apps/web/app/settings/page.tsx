import Link from "next/link";

import { DashboardShell, MiniStat, SectionHeader, SessionMetric } from "@/components/dashboard-shell";
import { PrivacyControls } from "@/components/privacy-controls";
import { getPrivacyStatus } from "@/lib/api";
import { formatCount } from "@/lib/format";

export const dynamic = "force-dynamic";

function parseConfigList(value: string | undefined): string[] {
  if (!value) {
    return [];
  }
  return value
    .split(/[,:]/)
    .map((entry) => entry.trim())
    .filter(Boolean);
}

function isTruthy(value: string | undefined): boolean {
  if (!value) {
    return false;
  }
  return ["1", "true", "yes", "on"].includes(value.trim().toLowerCase());
}

function ConfigRow({
  label,
  value,
}: {
  label: string;
  value: string;
}) {
  return (
    <div className="configRow">
      <span className="configLabel">{label}</span>
      <span className="configValue">{value}</span>
    </div>
  );
}

export default async function SettingsPage() {
  const apiUrl = process.env.ABSOLUTELY_API_URL?.trim() || "http://127.0.0.1:8000";
  const collectorBin = process.env.TRACEHOUSE_COLLECTOR_BIN?.trim() || "tracehouse-collector";
  const host = process.env.ABSOLUTELY_HOST?.trim() || "auto-detected host";
  const stateDir = process.env.ABSOLUTELY_STATE_DIR?.trim() || "local state directory";
  const paused = isTruthy(process.env.ABSOLUTELY_PAUSED);
  const excludeDirs = parseConfigList(process.env.ABSOLUTELY_EXCLUDE_DIRS);
  const excludeCommands = parseConfigList(process.env.ABSOLUTELY_EXCLUDE_COMMANDS);
  const privacy = await getPrivacyStatus();
  const privacyCounts = privacy.status?.counts ?? {};
  const privacyTotal = Object.values(privacyCounts).reduce((sum, count) => sum + count, 0);

  return (
    <DashboardShell
      active="settings"
      eyebrow="Settings"
      title="Local controls for capture, privacy, and recovery."
      description="These settings reflect the collector's current runtime configuration and the privacy rules it already understands."
      aside={
        <div className="statusGrid">
          <MiniStat label="Recording" value={paused ? "Paused" : "Active"} />
          <MiniStat label="Exclusion dirs" value={formatCount(excludeDirs.length)} />
          <MiniStat label="Excluded commands" value={formatCount(excludeCommands.length)} />
          <MiniStat label="Privacy rows" value={formatCount(privacyTotal)} />
          <MiniStat label="API" value={apiUrl} />
        </div>
      }
    >
      <section className="metricGrid">
        <SessionMetric
          label="Recording"
          value={paused ? "Paused" : "Active"}
          detail={paused ? "ABSOLUTELY_PAUSED is enabled in the current environment." : "Commands are being captured locally."}
        />
        <SessionMetric
          label="Excluded directories"
          value={formatCount(excludeDirs.length)}
          detail="configured through ABSOLUTELY_EXCLUDE_DIRS"
        />
        <SessionMetric
          label="Excluded commands"
          value={formatCount(excludeCommands.length)}
          detail="configured through ABSOLUTELY_EXCLUDE_COMMANDS"
        />
        <SessionMetric
          label="State location"
          value={stateDir}
          detail="collector pending captures and metadata stay on the local machine"
        />
        <SessionMetric
          label="Privacy rows"
          value={formatCount(privacyTotal)}
          detail="commands, sessions, repositories, commits, file changes, and summaries are exportable locally"
        />
      </section>

      <SectionHeader
        title="Runtime configuration"
        detail="The collector already reads these environment variables, so this page shows the actual local setup."
      />

      <div className="settingsGrid">
        <section className="card settingsPanel">
          <p className="settingsPanelTitle">Collector identity</p>
          <ConfigRow label="Host" value={host} />
          <ConfigRow label="Binary" value={collectorBin} />
          <ConfigRow label="API URL" value={apiUrl} />
        </section>

        <section className="card settingsPanel">
          <p className="settingsPanelTitle">Privacy posture</p>
          <div className="pillRow">
            <span className="pill">Secret redaction before storage</span>
            <span className="pill">Local-first persistence</span>
            <span className="pill">Pause and resume support</span>
            <span className="pill">Exclude directory support</span>
            <span className="pill">Exclude command support</span>
            <span className="pill">Encrypted backup export</span>
            <span className="pill">Delete-all data control</span>
          </div>
          <p className="settingsNote">
            Redaction, host-scoped recording, and exclusion rules are already enforced by the collector.
            Export, delete-all, and encrypted backup controls are now available from this page.
          </p>
        </section>
      </div>

      <SectionHeader
        title="Current exclusions"
        detail="These are the directories and command patterns the collector skips before events are persisted."
      />

      <div className="settingsGrid">
        <section className="card settingsPanel">
          <p className="settingsPanelTitle">Excluded directories</p>
          <div className="pillRow">
            {excludeDirs.length > 0 ? (
              excludeDirs.map((entry) => (
                <span key={entry} className="pill">
                  {entry}
                </span>
              ))
            ) : (
              <span className="settingsEmpty">No directories are excluded right now.</span>
            )}
          </div>
        </section>

        <section className="card settingsPanel">
          <p className="settingsPanelTitle">Excluded commands</p>
          <div className="pillRow">
            {excludeCommands.length > 0 ? (
              excludeCommands.map((entry) => (
                <span key={entry} className="pill">
                  {entry}
                </span>
              ))
            ) : (
              <span className="settingsEmpty">No command patterns are excluded right now.</span>
            )}
          </div>
        </section>
      </div>

      <SectionHeader
        title="Privacy actions"
        detail="Export a local backup, download an encrypted archive, or wipe the database when you need a clean slate."
      />

      <PrivacyControls status={privacy.status} error={privacy.error} />

      <SectionHeader
        title="Operational notes"
        detail="A few commands and environment variables keep the collector predictable on a developer machine."
        action={
          <Link href="/search" className="subtleLink">
            Search the evidence
          </Link>
        }
      />

      <div className="settingsGrid">
        <section className="card settingsPanel">
          <p className="settingsPanelTitle">Useful commands</p>
          <pre className="codeBlock">{`tracehouse-collector install-hooks
tracehouse-collector install-hooks --dry-run
tracehouse-collector uninstall-hooks
tracehouse-collector uninstall-hooks --dry-run
tracehouse-collector session-id`}</pre>
        </section>

        <section className="card settingsPanel">
          <p className="settingsPanelTitle">Environment variables</p>
          <pre className="codeBlock">{`ABSOLUTELY_PAUSED=1
ABSOLUTELY_EXCLUDE_DIRS=/tmp/build:/work/private
ABSOLUTELY_EXCLUDE_COMMANDS=pass,secret,token
TRACEHOUSE_COLLECTOR_BIN=tracehouse-collector
ABSOLUTELY_API_URL=${apiUrl}`}</pre>
        </section>
      </div>
    </DashboardShell>
  );
}
