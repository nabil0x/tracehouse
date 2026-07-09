"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

import { buildUrl, type PrivacyStatusRecord } from "@/lib/api";
import { formatCount } from "@/lib/format";

type PrivacyControlsProps = {
  status: PrivacyStatusRecord | null;
  error: string | null;
};

function triggerDownload(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.rel = "noreferrer";
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  // Give the browser a moment to start the download before releasing the blob URL.
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export function PrivacyControls({ status, error }: PrivacyControlsProps) {
  const [passphrase, setPassphrase] = useState("");
  const [deletePhrase, setDeletePhrase] = useState("");
  const [busy, setBusy] = useState<"export" | "delete" | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const router = useRouter();

  async function exportData(encrypt: boolean): Promise<void> {
    if (encrypt && !passphrase.trim()) {
      setMessage("Enter a passphrase before downloading an encrypted backup.");
      return;
    }

    setBusy("export");
    setMessage(null);
    try {
      const response = await fetch(buildUrl("/privacy/export"), {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          passphrase: encrypt ? passphrase : "",
        }),
      });
      if (!response.ok) {
        setMessage(`Export failed: ${response.status} ${response.statusText}`);
        return;
      }

      const blob = await response.blob();
      const filename = encrypt
        ? "tracehouse-encrypted-export.json"
        : "tracehouse-export.json";
      triggerDownload(blob, filename);
      setMessage(encrypt ? "Encrypted export downloaded." : "Export downloaded.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Export failed.");
    } finally {
      setBusy(null);
    }
  }

  async function deleteAllData(): Promise<void> {
    if (deletePhrase.trim() !== "DELETE ALL DATA") {
      setMessage("Type DELETE ALL DATA to confirm the wipe.");
      return;
    }

    setBusy("delete");
    setMessage(null);
    try {
      const response = await fetch(
        buildUrl(`/privacy/data?confirm=${encodeURIComponent("DELETE ALL DATA")}`),
        { method: "DELETE" },
      );
      if (!response.ok) {
        setMessage(`Delete failed: ${response.status} ${response.statusText}`);
        return;
      }
      setMessage("All local data has been deleted.");
      setDeletePhrase("");
      router.refresh();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Delete failed.");
    } finally {
      setBusy(null);
    }
  }

  const counts = status?.counts ?? {};
  const exportRows = Object.values(counts).reduce((total, count) => total + count, 0);

  return (
    <div className="settingsGrid privacyControlsGrid">
      <section className="card settingsPanel privacyPanel">
        <p className="settingsPanelTitle">Export data</p>
        <p className="settingsNote">
          Download a local snapshot of the database. Plain exports are JSON, and encrypted exports
          stay locked with a passphrase you choose in the browser.
        </p>

        <div className="privacyStatsRow">
          <div className="privacyStat">
            <span className="privacyStatValue">{formatCount(exportRows)}</span>
            <span className="privacyStatLabel">rows available</span>
          </div>
          <div className="privacyStat">
            <span className="privacyStatValue">
              {status?.export.encrypted_supported ? "Yes" : "No"}
            </span>
            <span className="privacyStatLabel">encrypted export</span>
          </div>
          <div className="privacyStat">
            <span className="privacyStatValue">
              {status?.encryption.supported ? "Fernet" : "Off"}
            </span>
            <span className="privacyStatLabel">encryption</span>
          </div>
        </div>

        <label className="privacyField">
          <span className="filterLabel">Passphrase for encrypted export</span>
          <input
            className="filterInput privacyInput"
            type="password"
            value={passphrase}
            onChange={(event) => setPassphrase(event.target.value)}
            placeholder="Choose a backup passphrase"
          />
        </label>

        <div className="privacyButtonRow">
          <button
            type="button"
            className="filterButton privacyButton"
            onClick={() => void exportData(false)}
            disabled={busy === "export"}
          >
            Export JSON
          </button>
          <button
            type="button"
            className="filterButton privacyButton"
            onClick={() => void exportData(true)}
            disabled={busy === "export"}
          >
            Export encrypted
          </button>
        </div>

        <p className="privacyNote">
          {status?.export.formats?.length
            ? `Supported formats: ${status.export.formats.join(", ")}`
            : "Supported formats: JSON and encrypted JSON."}
        </p>
      </section>

      <section className="card settingsPanel privacyDangerPanel">
        <p className="settingsPanelTitle">Delete everything</p>
        <p className="settingsNote">
          This permanently clears the local database. It removes commands, sessions, repositories,
          commits, file changes, embeddings, and summaries.
        </p>

        <label className="privacyField">
          <span className="filterLabel">Type DELETE ALL DATA to confirm</span>
          <input
            className="filterInput privacyInput"
            type="text"
            value={deletePhrase}
            onChange={(event) => setDeletePhrase(event.target.value)}
            placeholder="DELETE ALL DATA"
          />
        </label>

        <div className="privacyButtonRow">
          <button
            type="button"
            className="filterButton privacyDangerButton"
            onClick={() => void deleteAllData()}
            disabled={busy === "delete"}
          >
            Delete local data
          </button>
        </div>

        <p className="privacyNote">
          {status?.delete.confirmation
            ? `Confirmation phrase: ${status.delete.confirmation}`
            : "Confirmation phrase: DELETE ALL DATA"}
        </p>
      </section>

      {message || error ? (
        <section className="card settingsPanel privacyBanner">
          <p className="settingsPanelTitle">Privacy status</p>
          <p className="privacyStatusMessage">{message ?? error}</p>
        </section>
      ) : null}
    </div>
  );
}
