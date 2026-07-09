export type ApiListResponse<T> = {
  items: T[];
  total: number;
  limit: number;
  offset: number;
};

export type SessionSummary = {
  id: string;
  session_key: string;
  host: string;
  shell: string;
  started_at: string;
  last_seen_at: string;
  ended_at: string | null;
  session_type: string;
  metadata: Record<string, unknown>;
  commands_count: number;
  worked_ms: number;
  repositories_count: number;
  actor_count: number;
  kind: string;
  title: string;
  subtitle: string;
  timestamp: string;
};

export type CommandRecord = {
  id: string;
  session_id: string;
  session_key: string;
  repository_name: string | null;
  repository_root: string | null;
  command: string;
  cwd: string;
  timestamp_start: string;
  timestamp_end: string;
  duration_ms: number;
  exit_code: number;
  shell: string;
  host: string;
  actor_type: string;
  actor_name: string | null;
  agent_session_id: string;
  git_branch: string | null;
  git_commit_hash: string | null;
  stdout: string | null;
  stderr: string | null;
  metadata: Record<string, unknown>;
  redaction_findings: string[];
  kind: string;
  title: string;
  subtitle: string;
  timestamp: string;
};

export type RepositoryRecord = {
  id: string;
  host: string;
  name: string;
  root_path: string;
  branch: string | null;
  current_commit_hash: string | null;
  first_seen_at: string;
  last_seen_at: string;
  metadata: Record<string, unknown>;
};

export type AgentRecord = {
  id: string;
  host: string;
  actor_type: string;
  actor_name: string;
  agent_session_id: string;
  first_seen_at: string;
  last_seen_at: string;
  metadata: Record<string, unknown>;
};

export type CommitRecord = {
  id: string;
  repository_id: string;
  session_record_id: string | null;
  commit_hash: string;
  message: string;
  diff_summary: string | null;
  author_name: string | null;
  authored_at: string;
  committed_at: string;
  metadata: Record<string, unknown>;
  repository_name: string | null;
  repository_root: string | null;
  kind: string;
  title: string;
  subtitle: string;
  timestamp: string;
};

export type FileChangeRecord = {
  id: string;
  repository_id: string;
  commit_id: string | null;
  path: string;
  old_path: string | null;
  change_type: string;
  lines_added: number;
  lines_removed: number;
  metadata: Record<string, unknown>;
  repository_name: string | null;
  repository_root: string | null;
  commit_hash: string | null;
  message: string | null;
  committed_at: string | null;
  kind: string;
  title: string;
  subtitle: string;
  timestamp: string;
};

export type CommitDetailRecord = {
  commit: CommitRecord | null;
  file_changes: FileChangeRecord[];
  related_commands: CommandRecord[];
  errors: string[];
};

export type DailySummaryRecord = {
  id: string;
  summary_date: string;
  host: string;
  worked_ms: number;
  commands_count: number;
  commits_count: number;
  repositories: unknown[];
  top_tools: unknown[];
  summary_text: string;
  mistake_text: string | null;
  created_at: string;
  metadata: Record<string, unknown>;
  kind: string;
  title: string;
  subtitle: string;
  timestamp: string;
};

export type SearchResultRecord = {
  score: number;
  kind: string;
  title: string;
  subtitle: string;
  timestamp: string;
  command?: string;
  cwd?: string;
  session_key?: string;
  repository_name?: string | null;
  repository_root?: string | null;
  shell?: string;
  host?: string;
  actor_type?: string;
  actor_name?: string | null;
  exit_code?: number;
  duration_ms?: number;
  stdout?: string | null;
  stderr?: string | null;
  message?: string;
  diff_summary?: string | null;
  author_name?: string | null;
  commit_hash?: string;
  summary_text?: string;
  mistake_text?: string | null;
  repositories?: unknown[];
  top_tools?: unknown[];
  summary_date?: string;
  created_at?: string;
  metadata?: Record<string, unknown>;
};

export type SearchFilters = {
  query: string;
  host?: string;
  repository?: string;
  shell?: string;
  actor_type?: string;
  limit?: number;
};

export type PrivacyStatusRecord = {
  counts: Record<string, number>;
  export: {
    supported: boolean;
    formats: string[];
    encrypted_supported: boolean;
  };
  delete: {
    supported: boolean;
    confirmation: string;
  };
  encryption: {
    supported: boolean;
    scope: string;
    algorithm: string;
    kdf: string;
    iterations: number;
  };
};

export type TimelineFilters = {
  query?: string;
  host?: string;
  session_key?: string;
  repository?: string;
  shell?: string;
  exit_code?: number;
  actor_type?: string;
  actor_name?: string;
  git_commit_hash?: string;
  cwd?: string;
  started_after?: string;
  started_before?: string;
  limit?: number;
  offset?: number;
};

const FALLBACK_API_URL = "http://127.0.0.1:18400";

function apiBaseUrl(): string {
  return (
    process.env.ABSOLUTELY_API_URL?.trim() ||
    process.env.NEXT_PUBLIC_ABSOLUTELY_API_URL?.trim() ||
    FALLBACK_API_URL
  );
}

export function buildUrl(path: string): string {
  return `${apiBaseUrl().replace(/\/$/, "")}${path}`;
}

function buildQueryString(params: Record<string, string | number | undefined>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === "") {
      continue;
    }
    search.set(key, String(value));
  }
  const query = search.toString();
  return query ? `?${query}` : "";
}

async function safeFetchJson<T>(path: string): Promise<{ data: T | null; error: string | null }> {
  try {
    const response = await fetch(buildUrl(path), { cache: "no-store" });
    if (!response.ok) {
      return { data: null, error: `${response.status} ${response.statusText}` };
    }
    return { data: (await response.json()) as T, error: null };
  } catch (error) {
    return {
      data: null,
      error: error instanceof Error ? error.message : "Unknown API error",
    };
  }
}

export async function getSessions(limit = 12): Promise<{
  items: SessionSummary[];
  total: number;
  error: string | null;
}> {
  const result = await safeFetchJson<ApiListResponse<SessionSummary>>(`/sessions?limit=${limit}`);
  return {
    items: result.data?.items ?? [],
    total: result.data?.total ?? 0,
    error: result.error,
  };
}

export async function getSessionList(limit = 100): Promise<{
  items: SessionSummary[];
  total: number;
  error: string | null;
}> {
  const result = await safeFetchJson<ApiListResponse<SessionSummary>>(`/sessions?limit=${limit}`);
  return {
    items: result.data?.items ?? [],
    total: result.data?.total ?? 0,
    error: result.error,
  };
}

export async function getRepositories(limit = 100): Promise<{
  items: RepositoryRecord[];
  error: string | null;
}> {
  const result = await safeFetchJson<ApiListResponse<RepositoryRecord>>(`/repositories?limit=${limit}`);
  return {
    items: result.data?.items ?? [],
    error: result.error,
  };
}

export async function getAgents(limit = 100): Promise<{
  items: AgentRecord[];
  error: string | null;
}> {
  const result = await safeFetchJson<ApiListResponse<AgentRecord>>(`/agents?limit=${limit}`);
  return {
    items: result.data?.items ?? [],
    error: result.error,
  };
}

export async function getCommits(limit = 100): Promise<{
  items: CommitRecord[];
  error: string | null;
}> {
  const result = await safeFetchJson<ApiListResponse<CommitRecord>>(`/commits?limit=${limit}`);
  return {
    items: result.data?.items ?? [],
    error: result.error,
  };
}

export async function getCommitDetail(commitHash: string, repository?: string): Promise<{
  commit: CommitDetailRecord["commit"];
  file_changes: FileChangeRecord[];
  related_commands: CommandRecord[];
  errors: string[];
  error: string | null;
}> {
  const result = await safeFetchJson<CommitDetailRecord>(
    `/commits/${encodeURIComponent(commitHash)}${buildQueryString({
      repository,
    })}`,
  );
  return {
    commit: result.data?.commit ?? null,
    file_changes: result.data?.file_changes ?? [],
    related_commands: result.data?.related_commands ?? [],
    errors: result.data?.errors ?? [],
    error: result.error,
  };
}

export async function getDailySummaries(limit = 30): Promise<{
  items: DailySummaryRecord[];
  error: string | null;
}> {
  const result = await safeFetchJson<ApiListResponse<DailySummaryRecord>>(`/daily-summaries?limit=${limit}`);
  return {
    items: result.data?.items ?? [],
    error: result.error,
  };
}

export async function getSearch(filters: SearchFilters): Promise<{
  items: SearchResultRecord[];
  error: string | null;
  total: number;
}> {
  const result = await safeFetchJson<{ query: string; limit: number; total: number; items: SearchResultRecord[] }>(
    `/search${buildQueryString({
      query: filters.query,
      host: filters.host,
      repository: filters.repository,
      shell: filters.shell,
      actor_type: filters.actor_type,
      limit: filters.limit ?? 20,
    })}`,
  );
  return {
    items: result.data?.items ?? [],
    error: result.error,
    total: result.data?.total ?? result.data?.items?.length ?? 0,
  };
}

export async function getSessionDetail(sessionKey: string): Promise<{
  session: SessionSummary | null;
  commands: CommandRecord[];
  errors: string[];
}> {
  const encodedKey = encodeURIComponent(sessionKey);
  const [sessionResult, commandResult] = await Promise.all([
    safeFetchJson<ApiListResponse<SessionSummary>>(`/sessions?limit=1&session_key=${encodedKey}`),
    getTimeline({ limit: 200, session_key: sessionKey }),
  ]);

  return {
    session: sessionResult.data?.items?.[0] ?? null,
    commands: commandResult.items,
    errors: [sessionResult.error, commandResult.error].filter(Boolean) as string[],
  };
}

export async function getPrivacyStatus(): Promise<{
  status: PrivacyStatusRecord | null;
  error: string | null;
}> {
  const result = await safeFetchJson<PrivacyStatusRecord>(`/privacy`);
  return {
    status: result.data,
    error: result.error,
  };
}

export async function getTimeline(filters: TimelineFilters = {}): Promise<{
  items: CommandRecord[];
  total: number;
  error: string | null;
}> {
  const result = await safeFetchJson<ApiListResponse<CommandRecord>>(
    `/timeline${buildQueryString({
      query: filters.query,
      host: filters.host,
      session_key: filters.session_key,
      repository: filters.repository,
      shell: filters.shell,
      exit_code: filters.exit_code,
      actor_type: filters.actor_type,
      actor_name: filters.actor_name,
      git_commit_hash: filters.git_commit_hash,
      cwd: filters.cwd,
      started_after: filters.started_after,
      started_before: filters.started_before,
      limit: filters.limit ?? 100,
      offset: filters.offset ?? 0,
    })}`,
  );
  return {
    items: result.data?.items ?? [],
    total: result.data?.total ?? 0,
    error: result.error,
  };
}
