import Link from "next/link";

import {
  DashboardShell,
  EmptyState,
  MiniStat,
  SectionHeader,
} from "@/components/dashboard-shell";
import { CommandTranscript } from "@/components/command-transcript";
import { getSearch, type SearchResultRecord } from "@/lib/api";
import { formatCount, formatDate, formatTimestamp } from "@/lib/format";

export const dynamic = "force-dynamic";

type SearchParams = Record<string, string | string[] | undefined>;

type SearchFilters = {
  query?: string;
  host?: string;
  repository?: string;
  shell?: string;
  actor_type?: string;
  limit?: string;
};

const EXAMPLES = [
  { label: "Authentication bug", query: "authentication bug" },
  { label: "Docker networking", query: "docker networking" },
  { label: "Failed pytest", query: "failed pytest" },
  { label: "CUDA install", query: "CUDA install" },
  { label: "SSL certificate", query: "SSL certificate" },
];

function firstSearchParam(value: string | string[] | undefined): string | undefined {
  if (Array.isArray(value)) {
    return value[0];
  }
  return value;
}

function normalizeFilters(searchParams: SearchParams): SearchFilters {
  return {
    query: firstSearchParam(searchParams.query)?.trim() || undefined,
    host: firstSearchParam(searchParams.host)?.trim() || undefined,
    repository: firstSearchParam(searchParams.repository)?.trim() || undefined,
    shell: firstSearchParam(searchParams.shell)?.trim() || undefined,
    actor_type: firstSearchParam(searchParams.actor_type)?.trim() || undefined,
    limit: firstSearchParam(searchParams.limit)?.trim() || undefined,
  };
}

function parseLimit(value?: string): number {
  if (!value) {
    return 20;
  }
  const parsed = Number.parseInt(value, 10);
  if (Number.isNaN(parsed)) {
    return 20;
  }
  return Math.min(Math.max(parsed, 1), 100);
}

function countByKind(results: SearchResultRecord[]) {
  return results.reduce(
    (acc, item) => {
      acc[item.kind] = (acc[item.kind] ?? 0) + 1;
      return acc;
    },
    {} as Record<string, number>,
  );
}

function normalizeListItems(entries: unknown[] | undefined): string[] {
  return (entries ?? [])
    .map((entry) => {
      if (typeof entry === "string") {
        return entry.trim();
      }
      if (entry && typeof entry === "object") {
        const record = entry as Record<string, unknown>;
        return (
          (typeof record.label === "string" && record.label) ||
          (typeof record.name === "string" && record.name) ||
          (typeof record.tool === "string" && record.tool) ||
          (typeof record.repository === "string" && record.repository) ||
          (typeof record.path === "string" && record.path) ||
          ""
        ).trim();
      }
      return String(entry).trim();
    })
    .filter(Boolean);
}

function shortHash(hash?: string): string {
  if (!hash) {
    return "unknown";
  }
  return hash.slice(0, 12);
}

function resultLink(item: SearchResultRecord): string {
  if (item.kind === "command") {
    if (item.session_key) {
      return `/sessions/${encodeURIComponent(item.session_key)}`;
    }
    const repository = item.repository_name || item.repository_root;
    return repository ? `/timeline?repository=${encodeURIComponent(repository)}` : "/timeline";
  }

  if (item.kind === "commit") {
    const repository = item.repository_name || item.repository_root;
    if (!item.commit_hash) {
      return repository ? `/timeline?repository=${encodeURIComponent(repository)}` : "/timeline";
    }
    return repository
      ? `/commits/${encodeURIComponent(item.commit_hash)}?repository=${encodeURIComponent(repository)}`
      : `/commits/${encodeURIComponent(item.commit_hash)}`;
  }

  if (item.kind === "daily_summary") {
    return "/daily-reports";
  }

  return "/timeline";
}

function resultTitle(item: SearchResultRecord): string {
  if (item.kind === "command") {
    return item.command || item.title;
  }
  if (item.kind === "commit") {
    return item.message || item.title;
  }
  if (item.kind === "daily_summary") {
    return item.summary_text || item.title;
  }
  return item.title;
}

function resultDetail(item: SearchResultRecord): string {
  if (item.kind === "command") {
    return [
      item.repository_name || item.repository_root || "no repository",
      item.cwd,
      item.shell,
      item.actor_name || item.actor_type,
      item.exit_code !== undefined ? `exit ${item.exit_code}` : undefined,
    ]
      .filter(Boolean)
      .join(" · ");
  }

  if (item.kind === "commit") {
    return [
      item.repository_name || item.repository_root || "unknown repo",
      item.author_name || "unknown author",
      item.diff_summary || "",
      shortHash(item.commit_hash),
    ]
      .filter(Boolean)
      .join(" · ");
  }

  if (item.kind === "daily_summary") {
    return [
      item.host,
      item.summary_date ? formatDate(item.summary_date) : undefined,
      item.mistake_text || undefined,
    ]
      .filter(Boolean)
      .join(" · ");
  }

  return item.subtitle;
}

function ResultCard({ item }: { item: SearchResultRecord }) {
  const repositories = normalizeListItems(item.repositories).slice(0, 3);
  const tools = normalizeListItems(item.top_tools).slice(0, 3);

  return (
    <article className="card cardStrong detailHeaderCard searchResultCard">
      <div className="detailHeaderTop">
        <div>
          <p className="eyebrow">{item.kind.replace("_", " ")}</p>
          <p className="detailKey">{resultTitle(item)}</p>
          <p className="detailMeta">{resultDetail(item)}</p>
        </div>
        <Link href={resultLink(item)} className="pill">
          Open evidence
        </Link>
      </div>

      <div className="pillRow">
        <span className="pill">score {item.score.toFixed(2)}</span>
        {item.host ? <span className="pill">{item.host}</span> : null}
        {item.actor_name ? <span className="pill">{item.actor_name}</span> : null}
        {item.session_key ? <span className="pill">{item.session_key}</span> : null}
        {item.repository_name || item.repository_root ? (
          <span className="pill">{item.repository_name || item.repository_root}</span>
        ) : null}
        {item.timestamp ? <span className="pill">{formatTimestamp(item.timestamp)}</span> : null}
      </div>

      {item.kind === "command" ? (
        <CommandTranscript
          title="Transcript"
          stdout={item.stdout}
          stderr={item.stderr}
          note={<span>This is the captured terminal conversation behind the search hit.</span>}
        />
      ) : null}

      {item.kind === "commit" && item.diff_summary ? (
        <p className="commandDetail">
          <strong>Diff:</strong> {item.diff_summary}
        </p>
      ) : null}

      {item.kind === "daily_summary" ? (
        <div className="searchSummaryGrid">
          <div>
            <p className="searchSummaryLabel">Top tools</p>
            <div className="pillRow">
              {tools.length > 0 ? (
                tools.map((tool) => (
                  <span key={tool} className="pill">
                    {tool}
                  </span>
                ))
              ) : (
                <span className="searchEmpty">No tools captured.</span>
              )}
            </div>
          </div>

          <div>
            <p className="searchSummaryLabel">Repositories</p>
            <div className="pillRow">
              {repositories.length > 0 ? (
                repositories.map((repo) => (
                  <span key={repo} className="pill">
                    {repo}
                  </span>
                ))
              ) : (
                <span className="searchEmpty">No repository context.</span>
              )}
            </div>
          </div>
        </div>
      ) : null}
    </article>
  );
}

export default async function SearchPage(props: { searchParams: Promise<SearchParams> }) {
  const searchParams = await props.searchParams;
  const filters = normalizeFilters(searchParams);
  const query = filters.query ?? "";
  const limit = parseLimit(filters.limit);
  const result = query
    ? await getSearch({
        query,
        host: filters.host,
        repository: filters.repository,
        shell: filters.shell,
        actor_type: filters.actor_type,
        limit,
      })
    : null;

  const items = result?.items ?? [];
  const kindCounts = result ? countByKind(items) : {};
  const commands = kindCounts.command ?? 0;
  const commits = kindCounts.commit ?? 0;
  const summaries = kindCounts.daily_summary ?? 0;
  const queryLabel = query || "Search the evidence";

  return (
    <DashboardShell
      active="search"
      eyebrow="Search"
      title="Find the work trail by intent, not just text."
      description="Search across commands, commit messages, and daily summaries, then jump from the result to the underlying evidence."
      aside={
        <div className="statusGrid">
          <MiniStat label="Matches" value={formatCount(result?.total ?? 0)} />
          <MiniStat label="Commands" value={formatCount(commands)} />
          <MiniStat label="Commits" value={formatCount(commits)} />
          <MiniStat label="Summaries" value={formatCount(summaries)} />
        </div>
      }
    >
      {result?.error ? (
        <section className="card errorCard">
          <p className="errorTitle">Search is unavailable</p>
          <p className="errorDetail">{result.error}</p>
        </section>
      ) : null}

      <section className="card timelineFilterCard">
        <form action="/search" method="get" className="timelineFilters">
          <div className="timelineFilterGrid">
            <label className="filterField">
              <span className="filterLabel">Query</span>
              <input
                name="query"
                type="search"
                defaultValue={filters.query}
                placeholder="auth bug, docker networking, CUDA..."
                className="filterInput"
              />
            </label>

            <label className="filterField">
              <span className="filterLabel">Repository</span>
              <input
                name="repository"
                defaultValue={filters.repository}
                placeholder="/work/backend"
                className="filterInput"
              />
            </label>

            <label className="filterField">
              <span className="filterLabel">Host</span>
              <input name="host" defaultValue={filters.host} placeholder="laptop" className="filterInput" />
            </label>

            <label className="filterField">
              <span className="filterLabel">Shell</span>
              <input name="shell" defaultValue={filters.shell} placeholder="bash" className="filterInput" />
            </label>

            <label className="filterField">
              <span className="filterLabel">Actor type</span>
              <select name="actor_type" defaultValue={filters.actor_type ?? ""} className="filterInput">
                <option value="">Any</option>
                <option value="human">Human</option>
                <option value="agent">Agent</option>
              </select>
            </label>

            <label className="filterField">
              <span className="filterLabel">Limit</span>
              <select name="limit" defaultValue={String(limit)} className="filterInput">
                <option value="10">10</option>
                <option value="20">20</option>
                <option value="50">50</option>
                <option value="100">100</option>
              </select>
            </label>
          </div>

          <div className="filterActions">
            <button type="submit" className="pill filterButton">
              Search
            </button>
            <Link href="/search" className="pill">
              Clear
            </Link>
          </div>
        </form>
      </section>

      <section className="searchQuickGrid">
        {EXAMPLES.map((example) => (
          <Link
            key={example.query}
            href={`/search?query=${encodeURIComponent(example.query)}`}
            className="card searchQuickCard"
          >
            <p className="searchQuickLabel">{example.label}</p>
            <p className="searchQuickDetail">Try a focused query against commands, commits, and summaries.</p>
          </Link>
        ))}
      </section>

      {query ? (
        <>
          <SectionHeader
            title={`Results for "${queryLabel}"`}
            detail="Results are ranked by the local text search layer and linked back to the evidence they came from."
          />

          <div className="searchResultsList">
            {items.length > 0 ? (
              items.map((item, index) => (
                <ResultCard key={`${item.kind}:${index}:${item.timestamp}:${item.title}`} item={item} />
              ))
            ) : (
              <EmptyState
                title="No matches yet"
                detail="Try a broader query or remove filters. The search surface works best when you ask for the evidence in plain language."
              />
            )}
          </div>
        </>
      ) : (
        <EmptyState
          title="Search the evidence"
          detail="Enter a query above to search commands, commit messages, and daily summaries. The examples below are a good starting point."
        />
      )}
    </DashboardShell>
  );
}
