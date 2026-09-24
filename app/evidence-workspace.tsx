"use client";

import { useMemo, useRef, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import type { EvidenceSource } from "./brain-api";
import styles from "./evidence-workspace.module.css";

const MAX_FILE_BYTES = 10_000_000;
const ACCEPTED_EXTENSIONS = ".txt,.md,.markdown,.csv,.json,.vtt,.srt,.pdf,.docx";
const INTEGER_FORMAT = new Intl.NumberFormat("en");
const DATE_FORMAT = new Intl.DateTimeFormat("en-GB", {
  dateStyle: "medium",
  timeStyle: "short",
  timeZone: "UTC",
});

type MutationState =
  | { kind: "idle" }
  | { kind: "working"; message: string }
  | { kind: "success"; message: string }
  | { kind: "error"; message: string };

function formatBytes(value: number): string {
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${(value / (1024 * 1024)).toFixed(1)} MB`;
}

function formatDate(value: string | null): string {
  if (!value) return "Not supplied";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "Unknown" : `${DATE_FORMAT.format(date)} UTC`;
}

function retrievalLabel(source: EvidenceSource): string {
  if (source.retrieval_available) return "retrievable";
  if (source.integration_status === "revoked") return "retrieval revoked";
  if (source.integration_status === "revoking") return "retrieval revoking";
  if (source.integration_status === "revoke_failed") return "retrieval disabled";
  return "not retrievable";
}

function safeMutationMessage(status: number, action: "upload" | "delete"): string {
  if (status === 400 || status === 415 || status === 422) {
    return action === "upload"
      ? "The evidence file or metadata was not accepted. Check the supported format and fields."
      : "The evidence request was not accepted.";
  }
  if (status === 401) return "Your session is no longer authenticated.";
  if (status === 403) return "Your current role cannot perform this evidence action.";
  if (status === 404) return "The evidence source is no longer available to this account.";
  if (status === 409) return "That evidence action conflicts with the current source state.";
  if (status === 413) return "The upload is larger than the supported 10 MB file limit.";
  if (status === 429) return "Evidence requests are temporarily rate limited.";
  return "The evidence action could not be completed safely.";
}

export function EvidenceWorkspace({
  sources,
  mutationBase,
  canUpload,
}: {
  sources: EvidenceSource[];
  mutationBase: string | null;
  canUpload: boolean;
}) {
  const router = useRouter();
  const formRef = useRef<HTMLFormElement>(null);
  const [query, setQuery] = useState("");
  const [state, setState] = useState<MutationState>({ kind: "idle" });
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);

  const visibleSources = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (!needle) return sources;
    return sources.filter((source) => (
      source.title.toLowerCase().includes(needle)
      || source.filename.toLowerCase().includes(needle)
      || source.kind.includes(needle)
      || source.status.includes(needle)
      || source.integration_status.includes(needle)
      || retrievalLabel(source).includes(needle)
      || source.source_visibility.includes(needle)
    ));
  }, [query, sources]);

  async function submitUpload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!mutationBase || !canUpload) return;

    const form = event.currentTarget;
    const formData = new FormData(form);
    const file = formData.get("file");
    if (!(file instanceof File) || !file.name || !file.size) {
      setState({ kind: "error", message: "Choose a supported evidence file first." });
      return;
    }
    if (file.size > MAX_FILE_BYTES) {
      setState({ kind: "error", message: "The upload is larger than the supported 10 MB file limit." });
      return;
    }

    const occurredAt = formData.get("occurred_at");
    if (typeof occurredAt === "string" && occurredAt.trim()) {
      const parsed = new Date(occurredAt);
      if (Number.isNaN(parsed.getTime())) {
        setState({ kind: "error", message: "The evidence date is invalid." });
        return;
      }
      formData.set("occurred_at", parsed.toISOString());
    } else {
      formData.delete("occurred_at");
    }

    setState({ kind: "working", message: "Uploading and projecting governed evidence…" });
    try {
      const response = await fetch(`${mutationBase}/uploads`, {
        method: "POST",
        body: formData,
        credentials: "same-origin",
        headers: { "Idempotency-Key": crypto.randomUUID() },
      });
      if (!response.ok) {
        setState({ kind: "error", message: safeMutationMessage(response.status, "upload") });
        return;
      }
      formRef.current?.reset();
      setState({ kind: "success", message: "Evidence uploaded. Brain is using the governed source record." });
      router.refresh();
    } catch {
      setState({ kind: "error", message: "The evidence upload could not reach the secure Brain route." });
    }
  }

  async function deleteSource(sourceId: string) {
    if (!mutationBase) return;
    if (confirmDeleteId !== sourceId) {
      setConfirmDeleteId(sourceId);
      return;
    }

    setState({ kind: "working", message: "Deleting evidence through the governed lifecycle…" });
    try {
      const response = await fetch(`${mutationBase}/${encodeURIComponent(sourceId)}`, {
        method: "DELETE",
        credentials: "same-origin",
      });
      if (!response.ok) {
        setState({ kind: "error", message: safeMutationMessage(response.status, "delete") });
        return;
      }
      setConfirmDeleteId(null);
      setState({ kind: "success", message: "Evidence deleted. Searchable derivatives are removed by the backend lifecycle." });
      router.refresh();
    } catch {
      setState({ kind: "error", message: "The evidence deletion could not reach the secure Brain route." });
    }
  }

  return (
    <div className={styles.workspace}>
      <header className={styles.header}>
        <div>
          <p className={styles.eyebrow}>Files & evidence</p>
          <h2>Governed evidence workspace</h2>
          <p>
            Documents and transcripts keep source identity, visibility, hash and lifecycle state.
            Retrieval availability also reflects the current integration state, so revoked evidence is
            never presented as live intelligence.
          </p>
        </div>
        <div className={styles.summary} aria-label="Evidence summary">
          <span><b>{sources.length}</b> visible</span>
          <span><b>{sources.filter((item) => item.retrieval_available).length}</b> retrievable</span>
          <span><b>{sources.filter((item) => item.source_visibility === "restricted").length}</b> restricted</span>
        </div>
      </header>

      {canUpload ? (
        mutationBase ? (
          <form className={styles.uploadForm} ref={formRef} onSubmit={submitUpload}>
            <div className={styles.formHeading}>
              <div><strong>Add governed evidence</strong><span>Maximum file size 10 MB</span></div>
              <button disabled={state.kind === "working"} type="submit">
                {state.kind === "working" ? "Working…" : "Upload evidence"}
              </button>
            </div>
            <div className={styles.formGrid}>
              <label>
                <span>File</span>
                <input name="file" type="file" accept={ACCEPTED_EXTENSIONS} required />
              </label>
              <label>
                <span>Title <small>optional</small></span>
                <input name="title" maxLength={512} placeholder="Uses filename when empty" />
              </label>
              <label>
                <span>Evidence kind</span>
                <select name="kind" defaultValue="document">
                  <option value="document">Document</option>
                  <option value="transcript">Transcript</option>
                </select>
              </label>
              <label>
                <span>Visibility</span>
                <select name="visibility" defaultValue="organization">
                  <option value="organization">Organisation</option>
                  <option value="restricted">Restricted to uploader</option>
                </select>
              </label>
              <label>
                <span>Occurred at <small>optional</small></span>
                <input name="occurred_at" type="datetime-local" />
              </label>
            </div>
            <p className={styles.supportedTypes}>
              UTF-8 text, Markdown, CSV, JSON, VTT, SRT, text-extractable PDF and DOCX. OCR and encrypted PDFs are not silently attempted.
            </p>
          </form>
        ) : (
          <div className={styles.notice} role="status">
            Upload is implementation-ready but remains disabled until the authenticated same-origin WorkOS BFF is activated.
          </div>
        )
      ) : (
        <div className={styles.notice} role="status">
          This role can browse permitted evidence but cannot upload or delete sources.
        </div>
      )}

      {state.kind !== "idle" ? (
        <div className={styles.mutationState} data-kind={state.kind} role="status" aria-live="polite">
          {state.message}
        </div>
      ) : null}

      <div className={styles.toolbar}>
        <label>
          <span className={styles.visuallyHidden}>Filter evidence</span>
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Filter title, filename, visibility or retrieval state"
          />
        </label>
        <span>{visibleSources.length} shown</span>
      </div>

      <div className={styles.sourceList}>
        {visibleSources.length ? visibleSources.map((source) => (
          <article className={styles.sourceCard} key={source.id}>
            <div className={styles.sourceTop}>
              <div className={styles.sourceIdentity}>
                <span className={styles.kindIcon} aria-hidden="true">{source.kind === "transcript" ? "T" : "D"}</span>
                <div>
                  <strong>{source.title}</strong>
                  <small>{source.filename} · {formatBytes(source.byte_size)}</small>
                </div>
              </div>
              <div className={styles.badges}>
                <span data-status={source.status}>{source.status}</span>
                <span data-status={source.retrieval_available ? "active" : "unavailable"}>
                  {retrievalLabel(source)}
                </span>
                <span>{source.source_visibility}</span>
              </div>
            </div>

            <dl className={styles.metadata}>
              <div><dt>Chunks</dt><dd>{source.chunk_count}</dd></div>
              <div><dt>Extracted text</dt><dd>{INTEGER_FORMAT.format(source.extracted_char_count)} chars</dd></div>
              <div><dt>Occurred</dt><dd>{formatDate(source.occurred_at)}</dd></div>
              <div><dt>Uploaded</dt><dd>{formatDate(source.created_at)}</dd></div>
            </dl>

            <details className={styles.provenance}>
              <summary>Source provenance</summary>
              <dl>
                <div><dt>Evidence source</dt><dd><code>{source.id}</code></dd></div>
                <div><dt>SHA-256</dt><dd><code>{source.content_sha256}</code></dd></div>
                <div><dt>Integration</dt><dd><code>{source.integration_connection_id}</code></dd></div>
                <div><dt>Integration state</dt><dd>{source.integration_status}</dd></div>
                <div><dt>Retrieval available</dt><dd>{source.retrieval_available ? "yes" : "no"}</dd></div>
                <div><dt>Uploader</dt><dd><code>{source.created_by_user_id}</code></dd></div>
                <div><dt>Media type</dt><dd>{source.media_type}</dd></div>
                {source.last_error_code ? <div><dt>Error code</dt><dd>{source.last_error_code}</dd></div> : null}
                {source.deleted_at ? <div><dt>Deleted</dt><dd>{formatDate(source.deleted_at)}</dd></div> : null}
              </dl>
            </details>

            {source.can_delete && mutationBase ? (
              <div className={styles.sourceActions}>
                {confirmDeleteId === source.id ? (
                  <button className={styles.dangerButton} type="button" onClick={() => deleteSource(source.id)}>
                    Confirm permanent deletion
                  </button>
                ) : (
                  <button type="button" onClick={() => deleteSource(source.id)}>
                    Delete source
                  </button>
                )}
                {confirmDeleteId === source.id ? (
                  <button type="button" onClick={() => setConfirmDeleteId(null)}>Cancel</button>
                ) : null}
              </div>
            ) : null}
          </article>
        )) : (
          <p className={styles.emptyState}>No evidence sources match this view.</p>
        )}
      </div>
    </div>
  );
}
