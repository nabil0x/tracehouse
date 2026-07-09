import Link from "next/link";

import {
  DashboardShell,
  EmptyState,
  MiniStat,
  SectionHeader,
  SessionMetric,
} from "@/components/dashboard-shell";
import { getRepositories, type RepositoryRecord } from "@/lib/api";
import { formatCount, formatTimestamp } from "@/lib/format";

export const dynamic = "force-dynamic";

function uniqueCount(repositories: RepositoryRecord[], select: (repo: RepositoryRecord) => string | null) {
  return new Set(repositories.map(select).filter(Boolean)).size;
}

function metadataCount(metadata: Record<string, unknown>): number {
  return Object.keys(metadata).length;
}

function shortCommit(hash: string | null): string {
  if (!hash) {
    return "unknown";
  }
  return hash.slice(0, 12);
}

export default async function RepositoriesPage() {
  const { items: repositories, error } = await getRepositories(100);
  const latest = repositories[0];
  const hosts = uniqueCount(repositories, (repo) => repo.host);
  const branches = repositories.filter((repo) => Boolean(repo.branch)).length;
  const commits = repositories.filter((repo) => Boolean(repo.current_commit_hash)).length;
  const metadataFields = repositories.reduce((sum, repo) => sum + metadataCount(repo.metadata), 0);

  return (
    <DashboardShell
      active="repositories"
      eyebrow="Repositories"
      title="Workspace context, organized by repo."
      description="Track where work happened, which branch it touched, and when each repository was last seen."
      aside={
        <div className="statusGrid">
          <MiniStat label="Repositories" value={formatCount(repositories.length)} />
          <MiniStat label="Hosts" value={formatCount(hosts)} />
          <MiniStat label="Branches" value={formatCount(branches)} />
          <MiniStat label="Commit hashes" value={formatCount(commits)} />
        </div>
      }
    >
      {error ? (
        <section className="card errorCard">
          <p className="errorTitle">Repository data is unavailable</p>
          <p className="errorDetail">{error}</p>
        </section>
      ) : null}

      <section className="metricGrid">
        <SessionMetric
          label="Repositories"
          value={formatCount(repositories.length)}
          detail="tracked workspaces loaded from the local API"
        />
        <SessionMetric
          label="Hosts"
          value={formatCount(hosts)}
          detail="machines that have surfaced repository activity"
        />
        <SessionMetric
          label="Branches"
          value={formatCount(branches)}
          detail="repositories with a known current branch"
        />
        <SessionMetric
          label="Metadata fields"
          value={formatCount(metadataFields)}
          detail="auxiliary repository data available for enrichment"
        />
      </section>

      <SectionHeader
        title="Repository index"
        detail="Each repository card links back into the command timeline filtered to that workspace."
        action={
          <Link href="/timeline" className="subtleLink">
            Browse commands
          </Link>
        }
      />

      <div className="detailGrid">
        {repositories.length > 0 ? (
          repositories.map((repo) => {
            const repoLabel = repo.name || repo.root_path;
            const metadataFieldsCount = metadataCount(repo.metadata);
            return (
              <article key={repo.id} className="card cardStrong detailHeaderCard">
                <div className="detailHeaderTop">
                  <div>
                    <p className="eyebrow">{repo.host}</p>
                    <p className="detailKey">{repoLabel}</p>
                    <p className="detailMeta">{repo.root_path}</p>
                  </div>
                  <Link
                    href={`/timeline?repository=${encodeURIComponent(repo.root_path)}`}
                    className="pill"
                  >
                    Open timeline
                  </Link>
                </div>

                <div className="pillRow">
                  <span className="pill">branch {repo.branch || "unknown"}</span>
                  <span className="pill">commit {shortCommit(repo.current_commit_hash)}</span>
                  <span className="pill">first seen {formatTimestamp(repo.first_seen_at)}</span>
                  <span className="pill">last seen {formatTimestamp(repo.last_seen_at)}</span>
                  {metadataFieldsCount > 0 ? (
                    <span className="pill">{metadataFieldsCount} metadata fields</span>
                  ) : null}
                </div>
              </article>
            );
          })
        ) : (
          <EmptyState
            title="No repositories indexed yet"
            detail="Once commands run inside a project directory, repositories will appear here with their branch and commit context."
          />
        )}
      </div>

      {latest ? (
        <section className="card detailHeaderCard">
          <div className="detailHeaderTop">
            <div>
              <p className="eyebrow">Most recent repository</p>
              <p className="detailKey">{latest.name}</p>
              <p className="detailMeta">
                {latest.root_path} · last seen {formatTimestamp(latest.last_seen_at)}
              </p>
            </div>
            <Link href={`/timeline?repository=${encodeURIComponent(latest.root_path)}`} className="pill">
              View commands
            </Link>
          </div>

          <div className="pillRow">
            <span className="pill">{latest.host}</span>
            <span className="pill">branch {latest.branch || "unknown"}</span>
            <span className="pill">commit {shortCommit(latest.current_commit_hash)}</span>
          </div>
        </section>
      ) : null}
    </DashboardShell>
  );
}
