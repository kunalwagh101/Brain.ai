"use client";

import { FormEvent, useMemo, useState } from "react";
import type { AIRuntimeOption, AskBrainResponse } from "./brain-api";
import styles from "./ask-brain-panel.module.css";

function requestErrorMessage(status: number): string {
  if (status === 401) return "Your Brain session has expired. Sign in again and retry.";
  if (status === 403) return "Your current role is not allowed to use this AI capability.";
  if (status === 404) return "This organisation or AI resource is no longer available.";
  if (status === 409) return "Brain could not complete this request because its state changed. Retry.";
  if (status === 429) return "Brain is temporarily rate-limited. Retry shortly.";
  return "Ask Brain could not complete the request. No access was widened.";
}

export function AskBrainPanel({
  endpoint,
  runtimes,
}: {
  endpoint: string;
  runtimes: AIRuntimeOption[];
}) {
  const [question, setQuestion] = useState("");
  const [runtimeId, setRuntimeId] = useState(runtimes[0]?.model_configuration_id ?? "");
  const [result, setResult] = useState<AskBrainResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const runtime = useMemo(
    () => runtimes.find((item) => item.model_configuration_id === runtimeId) ?? null,
    [runtimeId, runtimes],
  );

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const normalized = question.trim();
    if (!normalized || !runtime || loading) return;

    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const response = await fetch(endpoint, {
        method: "POST",
        credentials: "same-origin",
        cache: "no-store",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question: normalized,
          provider_configuration_id: runtime.provider_configuration_id,
          model_configuration_id: runtime.model_configuration_id,
          search_mode: "hybrid",
          search_limit: 8,
        }),
      });
      if (!response.ok) throw new Error(requestErrorMessage(response.status));
      setResult(await response.json() as AskBrainResponse);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Ask Brain request failed safely.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className={styles.panel} aria-labelledby="ask-brain-title">
      <div className={styles.header}>
        <div>
          <p className={styles.eyebrow}>Ask Brain</p>
          <h2 id="ask-brain-title">Ask from authorised company evidence</h2>
        </div>
      </div>

      <form className={styles.form} onSubmit={submit}>
        <label htmlFor="ask-brain-question">Question</label>
        <textarea
          className={styles.textarea}
          id="ask-brain-question"
          value={question}
          maxLength={2000}
          onChange={(event) => setQuestion(event.target.value)}
          placeholder="What is blocking the current launch?"
          disabled={loading || !runtimes.length}
        />

        <label htmlFor="ask-brain-runtime">AI runtime</label>
        <select
          className={styles.select}
          id="ask-brain-runtime"
          value={runtimeId}
          onChange={(event) => setRuntimeId(event.target.value)}
          disabled={loading || !runtimes.length}
        >
          {runtimes.map((item) => (
            <option key={item.model_configuration_id} value={item.model_configuration_id}>
              {item.provider_display_name} · {item.model_display_name}
            </option>
          ))}
        </select>

        <button
          className={styles.button}
          type="submit"
          disabled={loading || !question.trim() || !runtime}
        >
          {loading ? "Checking evidence…" : "Ask Brain"}
        </button>
      </form>

      {!runtimes.length ? (
        <p className={styles.notice} role="status">
          No governed AI runtime is enabled for this organisation or role.
        </p>
      ) : null}
      {error ? <p className={styles.error} role="alert">{error}</p> : null}

      <div aria-live="polite" aria-atomic="false">
        {result?.status === "insufficient_evidence" ? (
          <div className={styles.insufficient} role="status">
            <strong>Not enough authorised evidence</strong>
            <p>{result.uncertainty ?? "Brain did not find enough evidence to answer safely."}</p>
          </div>
        ) : null}

        {result?.status === "answer" ? (
          <div className={styles.result}>
            <h3>Answer</h3>
            <p className={styles.answer}>{result.answer}</p>
            <h3>Claims and citations</h3>
            <ol className={styles.claims}>
              {result.claims.map((claim, index) => (
                <li key={`${claim.text}-${index}`}>
                  <p>{claim.text}</p>
                  <ul className={styles.citations}>
                    {claim.citation_ids.map((citationId) => {
                      const citation = result.citations.find(
                        (item) => item.evidence_id === citationId,
                      );
                      return (
                        <li key={citationId}>
                          {citation ? (
                            <details className={styles.citation}>
                              <summary>{citation.title}</summary>
                              <div className={styles.citationBody}>
                                <p>{citation.excerpt}</p>
                                <dl className={styles.provenance}>
                                  <dt>Evidence</dt><dd>{citation.evidence_id}</dd>
                                  <dt>Provider</dt><dd>{citation.source_provider}</dd>
                                  <dt>Object</dt>
                                  <dd>{citation.object_type} · {citation.object_external_id}</dd>
                                  <dt>Canonical event</dt><dd>{citation.canonical_event_id}</dd>
                                  <dt>Search document</dt><dd>{citation.document_id}</dd>
                                  {citation.source_event_id ? (
                                    <><dt>Source event</dt><dd>{citation.source_event_id}</dd></>
                                  ) : null}
                                </dl>
                              </div>
                            </details>
                          ) : (
                            <span>{citationId} · citation unavailable</span>
                          )}
                        </li>
                      );
                    })}
                  </ul>
                </li>
              ))}
            </ol>
            {result.uncertainty ? (
              <p className={styles.uncertainty}>
                <strong>Uncertainty:</strong> {result.uncertainty}
              </p>
            ) : null}
          </div>
        ) : null}
      </div>
    </section>
  );
}
