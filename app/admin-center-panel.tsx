"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import type { AdminCenter } from "./admin-center-api";
import styles from "./admin-center-panel.module.css";

function dateLabel(value: string | null): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return date.toLocaleDateString([], { year: "numeric", month: "short", day: "numeric" });
}

function statusLabel(value: string): string {
  return value.replaceAll("_", " ");
}

function safeError(status: number): string {
  if (status === 400 || status === 422) return "The admin action was not accepted. Check the submitted values.";
  if (status === 401) return "Your authenticated session has expired.";
  if (status === 403) return "Your current role cannot perform this admin action.";
  if (status === 404) return "The selected organisation resource is no longer available.";
  if (status === 409) return "The action conflicts with current organisation or credential state.";
  if (status === 413) return "The submitted admin payload is too large.";
  if (status === 429) return "Admin actions are temporarily rate limited.";
  if (status === 503) return "The governance backend or secret store is temporarily unavailable.";
  return "The admin action failed safely.";
}

function stringField(form: FormData, name: string): string {
  const value = form.get(name);
  return typeof value === "string" ? value.trim() : "";
}

function parseScopes(value: string): string[] {
  return [...new Set(value.split(/[\s,]+/).map((item) => item.trim()).filter(Boolean))];
}

function parseCredentials(value: string): Record<string, string> | null {
  try {
    const parsed = JSON.parse(value) as unknown;
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) return null;
    const entries = Object.entries(parsed as Record<string, unknown>);
    if (!entries.length || entries.length > 16) return null;
    const result: Record<string, string> = {};
    for (const [key, raw] of entries) {
      if (!key.trim() || key.length > 128 || typeof raw !== "string" || !raw || raw.length > 8192) {
        return null;
      }
      result[key.trim()] = raw;
    }
    return result;
  } catch {
    return null;
  }
}

const ALL_ROLES = ["owner", "admin", "executive", "manager", "member", "guest"] as const;

export function AdminCenterPanel({ admin }: { admin: AdminCenter }) {
  const router = useRouter();
  const [working, setWorking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [email, setEmail] = useState("");
  const [inviteRole, setInviteRole] = useState("member");
  const endpoint = `/api/brain/organizations/${encodeURIComponent(admin.organization_id)}/admin-center/actions`;
  const roleOptions = admin.viewer_role === "owner" ? ALL_ROLES : ALL_ROLES.filter((role) => !["owner", "admin"].includes(role));

  async function act(payload: Record<string, unknown>, success: string) {
    setWorking(true);
    setError(null);
    setNotice(null);
    try {
      const response = await fetch(endpoint, {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!response.ok) {
        setError(safeError(response.status));
        return false;
      }
      setNotice(success);
      router.refresh();
      return true;
    } catch {
      setError("The admin action could not reach the secure Brain route.");
      return false;
    } finally {
      setWorking(false);
    }
  }

  async function invite(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const normalized = email.trim().toLowerCase();
    if (!normalized) return;
    const ok = await act(
      { action: "member_invite", email: normalized, role: inviteRole },
      "Member added to this organisation.",
    );
    if (ok) setEmail("");
  }

  async function createProvider(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    const apiKey = stringField(data, "api_key");
    if (!apiKey) {
      setError("Enter the AI provider API key.");
      return;
    }
    const ok = await act(
      {
        action: "ai_provider_create",
        provider_key: stringField(data, "provider_key"),
        display_name: stringField(data, "display_name"),
        adapter_kind: stringField(data, "adapter_kind"),
        api_url: stringField(data, "api_url"),
        credentials: { api_key: apiKey },
      },
      "AI provider created. The credential value is not retained in this page.",
    );
    if (ok) form.reset();
  }

  async function createModel(event: FormEvent<HTMLFormElement>, providerId: string) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    const maxRaw = stringField(data, "max_output_tokens");
    const maxOutputTokens = maxRaw ? Number(maxRaw) : null;
    const ok = await act(
      {
        action: "ai_model_create",
        provider_id: providerId,
        model_key: stringField(data, "model_key"),
        display_name: stringField(data, "display_name"),
        enabled: true,
        max_output_tokens: maxOutputTokens,
      },
      "AI model added to the governed provider.",
    );
    if (ok) form.reset();
  }

  async function rotateProviderSecret(event: FormEvent<HTMLFormElement>, providerId: string) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    const apiKey = stringField(data, "api_key");
    if (!apiKey) {
      setError("Enter the replacement API key.");
      return;
    }
    const ok = await act(
      { action: "ai_provider_rotate", provider_id: providerId, credentials: { api_key: apiKey } },
      "AI provider credential rotated. The secret value is not retained in this page.",
    );
    if (ok) form.reset();
  }

  async function createService(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    const ok = await act(
      {
        action: "api_service_create",
        service_key: stringField(data, "service_key"),
        display_name: stringField(data, "display_name"),
        provider_name: stringField(data, "provider_name"),
        base_url: stringField(data, "base_url") || null,
      },
      "External API service added to the registry.",
    );
    if (ok) form.reset();
  }

  async function createGrant(event: FormEvent<HTMLFormElement>, serviceId: string) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    const credentials = parseCredentials(stringField(data, "credentials"));
    const scopes = parseScopes(stringField(data, "scopes"));
    if (!credentials) {
      setError("Credentials must be a JSON object containing only string values.");
      return;
    }
    if (!scopes.length) {
      setError("Enter at least one API scope.");
      return;
    }
    const expiresLocal = stringField(data, "expires_at");
    const expiresDate = expiresLocal ? new Date(expiresLocal) : null;
    if (expiresDate && Number.isNaN(expiresDate.getTime())) {
      setError("Expiry date is invalid.");
      return;
    }
    const expiresAt = expiresDate ? expiresDate.toISOString() : null;
    const ok = await act(
      {
        action: "api_grant_create",
        service_id: serviceId,
        grant_key: stringField(data, "grant_key"),
        display_name: stringField(data, "display_name"),
        owner_user_id: stringField(data, "owner_user_id"),
        environment: stringField(data, "environment"),
        scopes,
        expires_at: expiresAt,
        credentials,
      },
      "API grant created. Credential values are stored only in the configured secret store.",
    );
    if (ok) form.reset();
  }

  async function updateGrantMetadata(
    event: FormEvent<HTMLFormElement>,
    grantId: string,
    action: "api_grant_environment" | "api_grant_scopes",
  ) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    const reason = stringField(data, "reason") || null;
    const payload: Record<string, unknown> = { action, grant_id: grantId, reason };
    if (action === "api_grant_environment") payload.environment = stringField(data, "environment");
    else payload.scopes = parseScopes(stringField(data, "scopes"));
    const ok = await act(payload, action === "api_grant_environment" ? "API grant environment updated." : "API grant scopes updated.");
    if (ok) form.reset();
  }

  async function rotateGrantSecret(event: FormEvent<HTMLFormElement>, grantId: string) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    const credentials = parseCredentials(stringField(data, "credentials"));
    if (!credentials) {
      setError("Credentials must be a JSON object containing only string values.");
      return;
    }
    const ok = await act(
      {
        action: "api_grant_rotate",
        grant_id: grantId,
        credentials,
        reason: stringField(data, "reason") || null,
      },
      "API grant credential rotated. The secret value is not retained in this page.",
    );
    if (ok) form.reset();
  }

  return (
    <section className={styles.admin} aria-labelledby="admin-center-heading">
      <header className={styles.header}>
        <div>
          <p className={styles.eyebrow}>Workspace administration</p>
          <h2 id="admin-center-heading">Admin & governance</h2>
          <p>
            Current organisation controls and credential health. Brain exposes status and ownership here,
            never stored secret values. Secret-entry fields are transient and cleared after a successful save.
          </p>
        </div>
        <div className={styles.headerMeta}>
          <span className={styles.slug}>{admin.organization_slug}</span>
          <small>Signed in as {admin.viewer_role}</small>
        </div>
      </header>

      {notice ? <div className={styles.notice} role="status">{notice}</div> : null}
      {error ? <div className={styles.error} role="alert">{error}</div> : null}

      <div className={styles.metrics}>
        <article><span>Members</span><strong>{admin.summary.member_count}</strong></article>
        <article><span>Integrations</span><strong>{admin.summary.integration_count}</strong><small>{admin.summary.unhealthy_integration_count} need attention</small></article>
        <article><span>AI providers</span><strong>{admin.summary.ai_provider_count}</strong><small>{admin.summary.enabled_ai_model_count} enabled models</small></article>
        <article><span>API grants</span><strong>{admin.summary.active_api_grant_count}</strong><small>{admin.summary.expiring_api_grant_count} have expiry dates</small></article>
      </div>

      <div className={styles.grid}>
        <section className={styles.card}>
          <header><div><p className={styles.eyebrow}>People</p><h3>Members & roles</h3></div><span>{admin.members.length}</span></header>
          <form className={styles.inlineForm} onSubmit={invite}>
            <label>Existing Brain user email<input type="email" value={email} onChange={(event) => setEmail(event.target.value)} maxLength={320} required /></label>
            <label>Role<select value={inviteRole} onChange={(event) => setInviteRole(event.target.value)}>{roleOptions.map((role) => <option key={role} value={role}>{role}</option>)}</select></label>
            <button disabled={working || !email.trim()} type="submit">Add member</button>
          </form>
          <div className={styles.rows}>
            {admin.members.map((member) => {
              const protectedFromAdmin = admin.viewer_role !== "owner" && ["owner", "admin"].includes(member.role);
              return (
                <article key={member.membership_id}>
                  <div><strong>{member.display_name || member.email}</strong><small>{member.email}</small><small>Joined {dateLabel(member.joined_at)}</small></div>
                  <div className={styles.actions}>
                    <select aria-label={`Role for ${member.email}`} disabled={working || protectedFromAdmin} value={member.role} onChange={(event) => void act({ action: "member_role", membership_id: member.membership_id, role: event.target.value }, "Member role updated.")}>
                      {(admin.viewer_role === "owner" ? ALL_ROLES : ALL_ROLES.filter((role) => !["owner", "admin"].includes(role))).map((role) => <option key={role} value={role}>{role}</option>)}
                      {protectedFromAdmin ? <option value={member.role}>{member.role}</option> : null}
                    </select>
                    <button className={styles.dangerButton} disabled={working || protectedFromAdmin} onClick={() => { if (window.confirm(`Remove ${member.email} from ${admin.organization_name}?`)) void act({ action: "member_remove", membership_id: member.membership_id }, "Member removed."); }} type="button">Remove</button>
                  </div>
                </article>
              );
            })}
          </div>
        </section>

        <section className={styles.card}>
          <header><div><p className={styles.eyebrow}>Connections</p><h3>Integrations</h3></div><span>{admin.integrations.length}</span></header>
          <div className={styles.rows}>
            {admin.integrations.length ? admin.integrations.map((integration) => (
              <article key={integration.id}>
                <div><strong>{integration.display_name}</strong><small>{integration.provider} · {integration.scopes.length} scope(s)</small>{integration.last_error_code ? <small className={styles.warning}>Error: {integration.last_error_code}</small> : null}</div>
                <div className={styles.actions}>
                  <span data-status={integration.status}>{statusLabel(integration.status)}</span><small>Health: {statusLabel(integration.health)}</small><small>Last sync {dateLabel(integration.last_synced_at)}</small>
                  {integration.status !== "revoked" ? <button className={styles.dangerButton} disabled={working || integration.status === "revoking"} onClick={() => { if (window.confirm(`Revoke ${integration.display_name}? Stored credentials will be scheduled for deletion.`)) void act({ action: "integration_revoke", integration_id: integration.id }, "Integration revoked."); }} type="button">Revoke</button> : null}
                </div>
              </article>
            )) : <p className={styles.empty}>No managed integrations.</p>}
          </div>
        </section>

        <section className={styles.card}>
          <header><div><p className={styles.eyebrow}>AI governance</p><h3>Providers & models</h3></div><span>{admin.ai_providers.length}</span></header>
          <form className={styles.secretForm} onSubmit={(event) => void createProvider(event)}>
            <label>Provider key<input name="provider_key" placeholder="openai-primary" maxLength={64} required /></label>
            <label>Display name<input name="display_name" placeholder="Primary AI" maxLength={160} required /></label>
            <label>Adapter<select name="adapter_kind" defaultValue="openai_chat_completions"><option value="openai_chat_completions">OpenAI-compatible chat completions</option></select></label>
            <label className={styles.wideField}>API URL<input name="api_url" type="url" placeholder="https://api.openai.com/v1/chat/completions" maxLength={2048} required /></label>
            <label>API key<input name="api_key" type="password" autoComplete="new-password" maxLength={8192} required /></label>
            <button type="submit" disabled={working}>Add provider</button>
          </form>
          <div className={styles.providerList}>
            {admin.ai_providers.length ? admin.ai_providers.map((provider) => {
              const providerMutable = ["enabled", "disabled"].includes(provider.status);
              return (
                <article key={provider.id}>
                  <header>
                    <div><strong>{provider.display_name}</strong><small>{provider.provider_key} · {provider.adapter_kind}</small></div>
                    <div className={styles.actions}>
                      <span data-status={provider.status}>{statusLabel(provider.status)}</span>
                      {providerMutable ? <><button disabled={working} onClick={() => void act({ action: "ai_provider_status", provider_id: provider.id, enabled: provider.status !== "enabled" }, provider.status === "enabled" ? "AI provider disabled." : "AI provider enabled.")} type="button">{provider.status === "enabled" ? "Disable" : "Enable"}</button><button className={styles.dangerButton} disabled={working} onClick={() => { if (window.confirm(`Revoke ${provider.display_name}? Its stored provider credential will be removed.`)) void act({ action: "ai_provider_revoke", provider_id: provider.id }, "AI provider revoked."); }} type="button">Revoke</button></> : null}
                    </div>
                  </header>
                  <small className={styles.endpoint}>{provider.api_url}</small>
                  {providerMutable ? <form className={styles.secretForm} onSubmit={(event) => void rotateProviderSecret(event, provider.id)}><label>Replacement API key<input name="api_key" type="password" autoComplete="new-password" maxLength={8192} required /></label><button type="submit" disabled={working}>Rotate credential</button><small>Current secret is never displayed. Last rotated {dateLabel(provider.credential_rotated_at)}.</small></form> : null}
                  {providerMutable ? (
                    <form className={styles.secretForm} onSubmit={(event) => void createModel(event, provider.id)}>
                      <label>Model key<input name="model_key" placeholder="gpt-model" maxLength={255} required /></label>
                      <label>Display name<input name="display_name" maxLength={255} required /></label>
                      <label>Max output tokens<input name="max_output_tokens" type="number" min={1} max={1000000} /></label>
                      <button type="submit" disabled={working}>Add model</button>
                    </form>
                  ) : null}
                  <div className={styles.models}>{provider.models.map((model) => <div key={model.id}><span>{model.display_name}</span><small>{model.model_key}</small><button disabled={working || !providerMutable} onClick={() => void act({ action: "ai_model_status", model_id: model.id, enabled: !model.enabled }, model.enabled ? "AI model disabled." : "AI model enabled.")} type="button">{model.enabled ? "Disable" : "Enable"}</button></div>)}</div>
                </article>
              );
            }) : <p className={styles.empty}>No AI providers configured yet. Add the first governed provider above.</p>}
          </div>
        </section>

        <section className={styles.card}>
          <header><div><p className={styles.eyebrow}>External API governance</p><h3>Services & grants</h3></div><span>{admin.api_services.length}</span></header>
          <p className={styles.securityNote}>Credential JSON is submitted once to the server-side secret store and is never returned by this page.</p>
          <form className={styles.secretForm} onSubmit={(event) => void createService(event)}>
            <label>Service key<input name="service_key" placeholder="apollo" maxLength={64} required /></label>
            <label>Display name<input name="display_name" placeholder="Apollo" maxLength={160} required /></label>
            <label>Provider name<input name="provider_name" placeholder="Apollo.io" maxLength={160} required /></label>
            <label className={styles.wideField}>Base URL (optional)<input name="base_url" type="url" maxLength={2048} /></label>
            <button type="submit" disabled={working}>Add API service</button>
          </form>
          <div className={styles.providerList}>
            {admin.api_services.length ? admin.api_services.map((service) => (
              <article key={service.id}>
                <header><div><strong>{service.display_name}</strong><small>{service.provider_name} · {service.service_key}</small></div><span>{service.grants.length} grant(s)</span></header>
                {service.base_url ? <small className={styles.endpoint}>{service.base_url}</small> : null}
                <form className={styles.secretForm} onSubmit={(event) => void createGrant(event, service.id)}>
                  <label>Grant key<input name="grant_key" placeholder="production-read" maxLength={96} required /></label><label>Display name<input name="display_name" maxLength={160} required /></label>
                  <label>Owner<select name="owner_user_id" defaultValue={admin.members[0]?.user_id ?? ""} required>{admin.members.map((member) => <option key={member.user_id} value={member.user_id}>{member.email}</option>)}</select></label>
                  <label>Environment<input name="environment" defaultValue="production" maxLength={64} required /></label><label>Scopes<input name="scopes" placeholder="people.read, companies.read" maxLength={4096} required /></label><label>Expires at (optional)<input name="expires_at" type="datetime-local" /></label>
                  <label className={styles.wideField}>Credential JSON<textarea name="credentials" rows={3} maxLength={24000} autoComplete="off" spellCheck={false} placeholder='{"api_key":"..."}' required /></label><button type="submit" disabled={working || !admin.members.length}>Create grant</button>
                </form>
                <div className={styles.grants}>{service.grants.map((grant) => {
                  const mutable = ["active", "disabled"].includes(grant.status);
                  return (
                    <div key={grant.id} className={styles.grantRow}>
                      <div><strong>{grant.display_name}</strong><small>{grant.owner_email || grant.owner_user_id}</small></div>
                      <div className={styles.actions}><span data-status={grant.status}>{statusLabel(grant.status)}</span><small>{grant.environment} · {grant.scopes.join(", ")}</small><small>{grant.credential_present ? "credential stored" : "credential missing"} · {grant.usage_count} use(s)</small><small>Expires {dateLabel(grant.expires_at)} · rotated {dateLabel(grant.credential_rotated_at)}</small>{mutable ? <><button disabled={working} onClick={() => void act({ action: "api_grant_status", grant_id: grant.id, enabled: grant.status !== "active", reason: "Changed from Brain Admin Center" }, grant.status === "active" ? "API grant disabled." : "API grant enabled.")} type="button">{grant.status === "active" ? "Disable" : "Enable"}</button><button className={styles.dangerButton} disabled={working} onClick={() => { if (window.confirm(`Revoke API grant ${grant.display_name}? Its stored credential will be removed.`)) void act({ action: "api_grant_revoke", grant_id: grant.id, reason: "Revoked from Brain Admin Center" }, "API grant revoked."); }} type="button">Revoke</button></> : null}</div>
                      {mutable ? <div className={styles.grantEditors}>
                        <label>Owner<select value={grant.owner_user_id} disabled={working} onChange={(event) => void act({ action: "api_grant_owner", grant_id: grant.id, owner_user_id: event.target.value, reason: "Owner changed from Brain Admin Center" }, "API grant owner updated.")}>{admin.members.map((member) => <option key={member.user_id} value={member.user_id}>{member.email}</option>)}</select></label>
                        <form onSubmit={(event) => void updateGrantMetadata(event, grant.id, "api_grant_environment")}><label>Environment<input name="environment" defaultValue={grant.environment} maxLength={64} required /></label><input name="reason" type="hidden" value="Environment changed from Brain Admin Center" readOnly /><button type="submit" disabled={working}>Save</button></form>
                        <form onSubmit={(event) => void updateGrantMetadata(event, grant.id, "api_grant_scopes")}><label>Scopes<input name="scopes" defaultValue={grant.scopes.join(", ")} maxLength={4096} required /></label><input name="reason" type="hidden" value="Scopes changed from Brain Admin Center" readOnly /><button type="submit" disabled={working}>Save</button></form>
                        <form onSubmit={(event) => void rotateGrantSecret(event, grant.id)}><label>Replacement credential JSON<textarea name="credentials" rows={2} maxLength={24000} autoComplete="off" spellCheck={false} placeholder='{"api_key":"..."}' required /></label><input name="reason" type="hidden" value="Credential rotated from Brain Admin Center" readOnly /><button type="submit" disabled={working}>Rotate credential</button></form>
                      </div> : null}
                    </div>
                  );
                })}</div>
              </article>
            )) : <p className={styles.empty}>No external API services registered yet. Add the first service above.</p>}
          </div>
        </section>
      </div>
    </section>
  );
}
