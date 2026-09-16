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

export function AdminCenterPanel({ admin }: { admin: AdminCenter }) {
  return (
    <section className={styles.admin} aria-labelledby="admin-center-heading">
      <header className={styles.header}>
        <div>
          <p className={styles.eyebrow}>Workspace administration</p>
          <h2 id="admin-center-heading">Admin & governance</h2>
          <p>
            Current organisation controls and credential health. Brain exposes status and ownership here,
            never stored secret values.
          </p>
        </div>
        <span className={styles.slug}>{admin.organization_slug}</span>
      </header>

      <div className={styles.metrics}>
        <article><span>Members</span><strong>{admin.summary.member_count}</strong></article>
        <article><span>Integrations</span><strong>{admin.summary.integration_count}</strong><small>{admin.summary.unhealthy_integration_count} need attention</small></article>
        <article><span>AI providers</span><strong>{admin.summary.ai_provider_count}</strong><small>{admin.summary.enabled_ai_model_count} enabled models</small></article>
        <article><span>API grants</span><strong>{admin.summary.active_api_grant_count}</strong><small>{admin.summary.expiring_api_grant_count} have expiry dates</small></article>
      </div>

      <div className={styles.grid}>
        <section className={styles.card}>
          <header><div><p className={styles.eyebrow}>People</p><h3>Members & roles</h3></div><span>{admin.members.length}</span></header>
          <div className={styles.rows}>
            {admin.members.map((member) => (
              <article key={member.user_id}>
                <div><strong>{member.display_name || member.email}</strong><small>{member.email}</small></div>
                <div className={styles.meta}><span>{member.role}</span><small>Joined {dateLabel(member.joined_at)}</small></div>
              </article>
            ))}
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
                <div className={styles.meta}>
                  <span data-status={integration.status}>{statusLabel(integration.status)}</span>
                  <small>Health: {statusLabel(integration.health)}</small>
                  <small>Last sync {dateLabel(integration.last_synced_at)}</small>
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
                  <span data-status={provider.status}>{statusLabel(provider.status)}</span>
                </header>
                <small className={styles.endpoint}>{provider.api_url}</small>
                <div className={styles.models}>
                  {provider.models.map((model) => (
                    <div key={model.id}>
                      <span>{model.display_name}</span>
                      <small>{model.model_key}</small>
                      <b>{model.enabled ? "enabled" : "disabled"}</b>
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
                      <div className={styles.meta}>
                        <span data-status={grant.status}>{statusLabel(grant.status)}</span>
                        <small>{grant.environment} · {grant.scopes.length} scope(s)</small>
                        <small>{grant.credential_present ? "credential stored" : "credential missing"} · {grant.usage_count} use(s)</small>
                        <small>Expires {dateLabel(grant.expires_at)}</small>
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
