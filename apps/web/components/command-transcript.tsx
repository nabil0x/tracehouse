import type { ReactNode } from "react";

type CommandTranscriptProps = {
  stdout?: string | null;
  stderr?: string | null;
  title?: string;
  note?: ReactNode;
};

function hasContent(value?: string | null): value is string {
  return typeof value === "string" && value.trim().length > 0;
}

function lineCount(value: string): number {
  return value.trimEnd().split(/\r\n|\r|\n/).length;
}

function streamSummary(label: string, value: string): string {
  const count = lineCount(value);
  return `${label} ${count} line${count === 1 ? "" : "s"}`;
}

export function CommandTranscript({
  stdout,
  stderr,
  title = "Transcript",
  note,
}: CommandTranscriptProps) {
  const hasStdout = hasContent(stdout);
  const hasStderr = hasContent(stderr);

  if (!hasStdout && !hasStderr) {
    return null;
  }

  return (
    <details className="commandTranscript">
      <summary className="commandTranscriptSummary">
        <div className="commandTranscriptSummaryCopy">
          <span className="commandTranscriptLabel">{title}</span>
          <span className="commandTranscriptDetail">
            {hasStdout ? streamSummary("stdout", stdout) : null}
            {hasStdout && hasStderr ? " · " : null}
            {hasStderr ? streamSummary("stderr", stderr) : null}
          </span>
        </div>
        <span className="pill commandTranscriptPill">Open</span>
      </summary>

      <div className="commandTranscriptBody">
        {note ? <div className="commandTranscriptNote">{note}</div> : null}
        {hasStdout ? (
          <section className="commandTranscriptChunk">
            <p className="commandTranscriptChunkLabel">stdout</p>
            <pre className="commandTranscriptText">{stdout}</pre>
          </section>
        ) : null}
        {hasStderr ? (
          <section className="commandTranscriptChunk">
            <p className="commandTranscriptChunkLabel">stderr</p>
            <pre className="commandTranscriptText">{stderr}</pre>
          </section>
        ) : null}
      </div>
    </details>
  );
}
