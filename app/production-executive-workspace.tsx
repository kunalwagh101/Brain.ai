import {
  getExecutiveOverview,
  listOrganizations,
  listProjectStatuses,
  listRuntimeOptions,
} from "./brain-api";
import { LiveWorkspace } from "./live-workspace";

const EXECUTIVE_ROLES = new Set(["owner", "admin", "executive"]);

export async function ProductionExecutiveWorkspace({
  accessToken,
  signedInName,
  requestedOrganizationId,
}: {
  accessToken: string;
  signedInName: string;
  requestedOrganizationId?: string | null;
}) {
  const organizations = await listOrganizations(accessToken);
  if (!organizations.length) {
    return (
      <main className="workspace">
        <section className="panel" role="status">
          <p className="eyebrow">Brain workspace</p>
          <h1>No organisation membership</h1>
          <p>Your authenticated WorkOS identity is not currently a member of a Brain organisation.</p>
        </section>
      </main>
    );
  }

  const organization = requestedOrganizationId
    ? organizations.find((item) => item.id === requestedOrganizationId)
    : organizations[0];

  if (!organization) {
    return (
      <main className="workspace">
        <section className="panel" role="alert">
          <p className="eyebrow">Permission boundary</p>
          <h1>Organisation unavailable</h1>
          <p>The requested organisation is not in your current authenticated membership list.</p>
        </section>
      </main>
    );
  }

  if (!EXECUTIVE_ROLES.has(organization.role)) {
    return (
      <main className="workspace">
        <section className="panel" role="status">
          <p className="eyebrow">Permission boundary</p>
          <h1>Executive overview is not available for this role</h1>
          <p>
            You are signed in to {organization.name} as {organization.role}. Brain does not widen
            organisation-wide audit access merely because the frontend can see the organisation.
          </p>
        </section>
      </main>
    );
  }

  const [overview, projects, runtimes] = await Promise.all([
    getExecutiveOverview(accessToken, organization.id),
    listProjectStatuses(accessToken, organization.id),
    listRuntimeOptions(accessToken, organization.id),
  ]);

  return (
    <LiveWorkspace
      organization={organization}
      overview={overview}
      projects={projects}
      runtimes={runtimes}
      signedInName={signedInName}
    />
  );
}
