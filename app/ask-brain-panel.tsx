"use client";

import { FormEvent, useMemo, useState } from "react";
import type { AIRuntimeOption, AskBrainResponse } from "./brain-api";

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
      if (!response.ok) {
        const payload = await response.json().catch(() => null);
        const detail = payload && typeof payload === "object" && "detail" in payload
          ? JSON.stringify(payload.detail)
          : `HTTP ${response.status}`;
        throw new Error(detail);
      }
      setResult(await response.json() as AskBrainResponse);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Ask Brain request failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="panel" aria-labelledby="ask-brain-title">
      <div className="panelHeader">
        <div><p className="eyebrow">Ask Brain</p><h2 id="ask-brain-title">Ask from authorised company evidence</h2></div>
      </div>

      <form onSubmit={submit}>
        <label htmlFor="ask-brain-question">Question</label>
        <textarea
          id="ask-brain-question"
          value={question}
          maxLength={2000}
          onChange={(event) => setQuestion(event.target.value)}
          placeholder="What is blocking the current launch?"
          disabled={loading || !runtimes.length}
          style={{ width: "100%", minHeight: 96, marginTop: 8, padding: 12 }}
        />

        <label htmlFor="ask-brain-runtime" style={{ display: "block", marginTop: 12 }}>AI runtime</label>
        <select
          id="ask-brain-runtime"
          value={runtimeId}
          onChange={(event) => setRuntimeId(event.target.value)}
          disabled={loading || !runtimes.length}
          style={{ width: "100%", minHeight: 40, marginTop: 8 }}
        >
          {runtimes.map((item) => (
            <option key={item.model_configuration_id} value={item.model_configuration_id}>
              {item.provider_display_name} · {item.model_display_name}
            </option>
          ))}
        </select>

        <button className="primaryButton" type="submit" disabled={loading || !question.trim() || !runtime} style={{ marginTop: 12 }}>
          {loading ? "Checking evidence…" : "Ask Brain"}
        </button>
      </form>

      {!runtimes.length ? <p role="status">No governed AI runtime is enabled for this organisation.</p> : null}
      {error ? <p role="alert">Ask Brain could not complete: {error}</p> : null}

      {result?.status === "insufficient_evidence" ? (
        <div role="status" style={{ marginTop: 16 }}>
          <strong>Not enough authorised evidence</strong>
          <p>{result.uncertainty ?? "Brain did not find enough evidence to answer safely."}</p>
        </div>
      ) : null}

      {result?.status === "answer" ? (
        <div style={{ marginTop: 16 }}>
          <h3>Answer</h3>
          <p>{result.answer}</p>
          <h3>Claims and citations</h3>
          <ol>
            {result.claims.map((claim, index) => (
              <li key={`${claim.text}-${index}`}>
                <p>{claim.text}</p>
                <ul>
                  {claim.citation_ids.map((citationId) => {
                    const citation = result.citations.find((item) => item.evidence_id === citationId);
                    return (
                      <li key={citationId}>
                        <strong>{citation?.title ?? citationId}</strong>
                        {citation ? <p>{citation.excerpt}</p> : null}
                      </li>
                    );
                  })}
                </ul>
              </li>
            ))}
          </ol>
          {result.uncertainty ? <p><strong>Uncertainty:</strong> {result.uncertainty}</p> : null}
        </div>
      ) : null}
    </section>
  );
}
