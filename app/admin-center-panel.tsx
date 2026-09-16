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
  if (status === 409) return "The action conflicts with current organisation state, such as the last-owner rule.";
  if (status === 429) return "Admin actions are temporarily rate limited.";
  if (status === 503) return "The governance backend or secret store is temporarily unavailable.";
  return "The admin action failed safely.";
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

  return (
    <section className={styles.admin} aria-labelledby="admin-center-heading">
      <header className={styles.header}>
        <div>
          <p className={styles.eyebrow}>Workspace administration</p>
          <h2 id="admin-center-heading">Admin & governance</h2>
          <p>
            Current organisation controls and credential health. Brain exposes status and ownership here,
            never stored secret values. Destructive actions remain enforced again by FastAPI.
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
            <label>
              Existing Brain user email
              <input type="email" value={email} onChange={(event) => setEmail(event.target.value)} maxLength={320} required />
            </label>
            <label>
              Role
              <select value={inviteRole} onChange={(event) => setInviteRole(event.target.value)}>
                {roleOptions.map((role) => <option key={role} value={role}>{role}</option>)}
              </select>
            </label>
            <button disabled={working || !email.trim()} type="submit">Add member</button>
          </form>
          <div className={styles.rows}>
            {admin.members.map((member) => {
              const protectedFromAdmin = admin.viewer_role !== "owner" && ["owner", "admin"].includes(member.role);
              return (
                <article key={member.membership_id}>
                  <div><strong>{member.display_name || member.email}</strong><small>{member.email}</small><small>Joined {dateLabel(member.joined_at)}</small></div>
                  <div className={styles.actions}>
                    <select
                      aria-label={`Role for ${member.email}`}
                      disabled={working || protectedFromAdmin}
                      value={member.role}
                      onChange={(event) => void act(
                        { action: "member_role", membership_id: member.membership_id, role: event.target.value },
                        "Member role updated.",
                      )}
                    >
                      {(admin.viewer_role === "owner" ? ALL_ROLES : ALL_ROLES.filter((role) => !["owner", "admin"].includes(role))).map((role) => (
                        <option key={role} value={role}>{role}</option>
                      ))}
                      {protectedFromAdmin ? <option value={member.role}>{member.role}</option> : null}
                    </select>
                    <button
                      className={styles.dangerButton}
                      disabled={working || protectedFromAdmin}
                      onClick={() => {
                        if (!window.confirm(`Remove ${member.email} from ${admin.organization_name}?`)) return;
                        void act({ action: "member_remove", membership_id: member.membership_id }, "Member removed.");
                      }}
                      type="button"
                    >Remove</button>
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
                <div>
                  <strong>{integration.display_name}</strong>
                  <small>{integration.provider} · {integration.scopes.length} scope(s)</small>
                  {integration.last_error_code ? <small className={styles.warning}>Error: {integration.last_error_code}</small> : null}
                </div>
                <div className={styles.actions}>
                  <span data-status={integration.status}>{statusLabel(integration.status)}</span>
                  <small>Health: {statusLabel(integration.health)}</small>
                  <small>Last sync {dateLabel(integration.last_synced_at)}</small>
                  {integration.status !== "revoked" ? (
                    <button
                      className={styles.dangerButton}
                      disabled={working || integration.status === "revoking"}
                      onClick={() => {
                        if (!window.confirm(`Revoke ${integration.display_name}? Stored credentials will be scheduled for deletion.`)) return;
                        void act({ action: "integration_revoke", integration_id: integration.id }, "Integration revoked.");
                      }}
                      type="button"
                    >Revoke</button>
                  ) : null}
                </div>
              </article>
            )) : <p className={styles.empty}>No managed integrations.</p>}
          </div>
        </section>

        <section className={styles.card}>
          <header><div><p className={styles.eyebrow}>AI governance</p><h3>Providers & models</h3></div><span>{admin.ai_providers.length}</span></header>
          <div className={styles.providerList}>
            {admin.ai_providers.length ? admin.ai_providers.map((provider) => (
              <article key={provider.id}>
                <header>
                  <div><strong>{provider.display_name}</strong><small>{provider.provider_key} · {provider.adapter_kind}</small></div>
                  <div className={styles.actions}>
                    <span data-status={provider.status}>{statusLabel(provider.status)}</span>
                    {provider.status !== "revoked" ? (
                      <>
                        <button disabled={working} onClick={() => void act(
                          { action: "ai_provider_status", provider_id: provider.id, enabled: provider.status !== "enabled" },
                          provider.status === "enabled" ? "AI provider disabled." : "AI provider enabled.",
                        )} type="button">{provider.status === "enabled" ? "Disable" : "Enable"}</button>
                        <button className={styles.dangerButton} disabled={working} onClick={() => {
                          if (!window.confirm(`Revoke ${provider.display_name}? Its stored provider credential will be removed.`)) return;
                          void act({ action: "ai_provider_revoke", provider_id: provider.id }, "AI provider revoked.");
                        }} type="button">Revoke</button>
                      </>
                    ) : null}
                  </div>
                </header>
                <small className={styles.endpoint}>{provider.api_url}</small>
                <div className={styles.models}>
                  {provider.models.map((model) => (
                    <div key={model.id}>
                      <span>{model.display_name}</span>
                      <small>{model.model_key}</small>
                      <button
                        disabled={working || provider.status === "revoked"}
                        onClick={() => void act(
                          { action: "ai_model_status", model_id: model.id, enabled: !model.enabled },
                          model.enabled ? "AI model disabled." : "AI model enabled.",
                        )}
                        type="button"
                      >{model.enabled ? "Disable" : "Enable"}</button>
                    </div>
                  ))}
                </div>
              </article>
            )) : <p className={styles.empty}>No AI providers configured.</p>}
          </div>
        </section>

        <section className={styles.card}>
          <header><div><p className={styles.eyebrow}>External API governance</p><h3>Services & grants</h3></div><span>{admin.api_services.length}</span></header>
          <div className={styles.providerList}>
            {admin.api_services.length ? admin.api_services.map((service) => (
              <article key={service.id}>
                <header><div><strong>{service.display_name}</strong><small>{service.provider_name} · {service.service_key}</small></div><span>{service.grants.length} grant(s)</span></header>
                {service.base_url ? <small className={styles.endpoint}>{service.base_url}</small> : null}
                <div className={styles.grants}>
                  {service.grants.map((grant) => (
                    <div key={grant.id}>
                      <div><strong>{grant.display_name}</strong><small>{grant.owner_email || grant.owner_user_id}</small></div>
                      <div className={styles.actions}>
                        <span data-status={grant.status}>{statusLabel(grant.status)}</span>
                        <small>{grant.environment} · {grant.scopes.length} scope(s)</small>
                        <small>{grant.credential_present ? "credential stored" : "credential missing"} · {grant.usage_count} use(s)</small>
                        <small>Expires {dateLabel(grant.expires_at)}</small>
                        {!["revoked", "revoking", "expired"].includes(grant.status) ? (
                          <>
                            <button disabled={working} onClick={() => void act(
                              { action: "api_grant_status", grant_id: grant.id, enabled: grant.status !== "active", reason: "Changed from Brain Admin Center" },
                              grant.status === "active" ? "API grant disabled." : "API grant enabled.",
                            )} type="button">{grant.status === "active" ? "Disable" : "Enable"}</button>
                            <button className={styles.dangerButton} disabled={working} onClick={() => {
                              if (!window.confirm(`Revoke API grant ${grant.display_name}? Its stored credential will be removed.`)) return;
                              void act({ action: "api_grant_revoke", grant_id: grant.id, reason: "Revoked from Brain Admin Center" }, "API grant revoked.");
                            }} type="button">Revoke</button>
                          </>
                        ) : null}
                      </div>
                    </div>
                  ))}
                </div>
              </article>
            )) : <p className={styles.empty}>No external API services registered.</p>}
          </div>
        </section>
      </div>
    </section>
  );
}
