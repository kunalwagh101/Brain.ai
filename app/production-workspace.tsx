import {
  getExecutiveOverview,
  listOrganizations,
  listProjectStatuses,
  listWorkspaceNavigation,
} from "./brain-api";
import { WorkspaceShell } from "./workspace-shell";

const EXECUTIVE_ROLES = new Set(["owner", "admin", "executive"]);

export async function ProductionWorkspace({
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
      <main role="status">
        <h1>No organisation membership</h1>
        <p>Your authenticated identity is not currently a member of a Brain organisation.</p>
      </main>
    );
  }

  const organization = requestedOrganizationId
    ? organizations.find((item) => item.id === requestedOrganizationId)
    : organizations[0];

  if (!organization) {
    return (
      <main role="alert">
        <h1>Organisation unavailable</h1>
        <p>The requested organisation is not in your current authenticated membership list.</p>
      </main>
    );
  }

  const [navigation, projects, overview] = await Promise.all([
    listWorkspaceNavigation(accessToken, organization.id),
    listProjectStatuses(accessToken, organization.id),
    EXECUTIVE_ROLES.has(organization.role)
      ? getExecutiveOverview(accessToken, organization.id)
      : Promise.resolve(null),
  ]);

  return (
    <WorkspaceShell
      organization={organization}
      navigation={navigation}
      projects={projects}
      overview={overview}
      signedInName={signedInName}
    />
  );
}
