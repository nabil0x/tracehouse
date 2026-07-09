import type { ReactNode } from "react";
import Link from "next/link";

import { formatCount } from "@/lib/format";

const NAV_ITEMS = [
  { href: "/", label: "Overview", key: "overview" as const },
  { href: "/search", label: "Search", key: "search" as const },
  { href: "/timeline", label: "Timeline", key: "timeline" as const },
  { href: "/sessions", label: "Sessions", key: "sessions" as const },
  { href: "/analytics", label: "Analytics", key: "analytics" as const },
  { href: "/daily-reports", label: "Daily Reports", key: "dailyReports" as const },
  { href: "/repositories", label: "Repositories", key: "repositories" as const },
  { href: "/agents", label: "Agents", key: "agents" as const },
  { href: "/settings", label: "Settings", key: "settings" as const },
];

type DashboardShellProps = {
  active:
    | "overview"
    | "search"
    | "timeline"
    | "sessions"
    | "analytics"
    | "dailyReports"
    | "repositories"
    | "agents"
    | "settings";
  eyebrow: string;
  title: string;
  description: string;
  children: ReactNode;
  aside?: ReactNode;
};

function apiLabel(): string {
  return process.env.ABSOLUTELY_API_URL?.trim() || "http://127.0.0.1:18400";
}

export function DashboardShell({
  active,
  eyebrow,
  title,
  description,
  children,
  aside,
}: DashboardShellProps) {
  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">
          <span className="brandMark" aria-hidden="true" />
          <div>
            <div className="brandName">Tracehouse</div>
            <div className="brandTag">Terminal intelligence, local-first</div>
          </div>
        </div>

        <nav className="nav" aria-label="Primary">
          {NAV_ITEMS.map((item) => (
            <Link
              key={item.key}
              href={item.href}
              className="navLink"
              data-active={active === item.key ? "true" : "false"}
            >
              {item.label}
            </Link>
          ))}
        </nav>

        <section className="sidebarNote" aria-label="Roadmap">
          <p className="sidebarNoteLabel">Still to build</p>
          <ul className="sidebarNoteList">
            <li>Packaging</li>
            <li>Install</li>
            <li>Uninstall</li>
          </ul>
        </section>

        <div className="sidebarFooter">
          <span className="sidebarFooterLabel">API</span>
          <span className="sidebarFooterValue">{apiLabel()}</span>
        </div>
      </aside>

      <main className="content">
        <header className="hero">
          <div className="heroCopy">
            <p className="eyebrow">{eyebrow}</p>
            <h1 className="headline">{title}</h1>
            <p className="lede">{description}</p>
          </div>
          {aside ? <div className="heroAside">{aside}</div> : null}
        </header>

        <div className="pageBody">{children}</div>
      </main>
    </div>
  );
}

export function SessionMetric({
  label,
  value,
  detail,
}: {
  label: string;
  value: string;
  detail?: string;
}) {
  return (
    <article className="card metricCard">
      <p className="metricLabel">{label}</p>
      <p className="metricValue">{value}</p>
      {detail ? <p className="metricDetail">{detail}</p> : null}
    </article>
  );
}

export function SectionHeader({
  title,
  detail,
  action,
}: {
  title: string;
  detail?: string;
  action?: ReactNode;
}) {
  return (
    <div className="sectionHeader">
      <div>
        <h2 className="sectionTitle">{title}</h2>
        {detail ? <p className="sectionDetail">{detail}</p> : null}
      </div>
      {action ? <div className="sectionAction">{action}</div> : null}
    </div>
  );
}

export function EmptyState({
  title,
  detail,
}: {
  title: string;
  detail: string;
}) {
  return (
    <div className="card emptyState">
      <p className="emptyStateTitle">{title}</p>
      <p className="emptyStateDetail">{detail}</p>
    </div>
  );
}

export function MiniStat({
  label,
  value,
}: {
  label: string;
  value: number | string;
}) {
  return (
    <div className="miniStat">
      <span className="miniStatValue">{typeof value === "number" ? formatCount(value) : value}</span>
      <span className="miniStatLabel">{label}</span>
    </div>
  );
}
