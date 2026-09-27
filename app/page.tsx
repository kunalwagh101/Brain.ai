import { signOut } from "@workos-inc/authkit-nextjs";
import { redirect } from "next/navigation";
import { demoAvailable, getBrainSession, revokeDemoSession } from "./brain-session";
import { ProductionWorkspace } from "./production-workspace";
import { BrainApiError, createOrganization } from "./brain-api";
import { workspaceCreationInput } from "./workspace-creation-input";
import type { CreateWorkspaceState } from "./create-workspace-form";

export const dynamic = "force-dynamic";

export default async function Home({
  searchParams,
}: {
  searchParams: Promise<{
    organizationId?: string;
    channelId?: string;
    dmId?: string;
    messageId?: string;
  }>;
}) {
  const { user, accessToken, isDemo } = await getBrainSession();
  if (!user || !accessToken) redirect(demoAvailable() ? "/demo-signup" : "/sign-in");
  const params = await searchParams;
  const signedInName = [user.firstName, user.lastName].filter(Boolean).join(" ")
    || user.email
    || "Brain user";

  async function signOutAction(formData: FormData) {
    "use server";
    void formData;
    const current = await getBrainSession();
    if (current.isDemo && current.accessToken) {
      await revokeDemoSession(current.accessToken);
      redirect("/demo-signup?ended=1");
    }
    await signOut();
  }

  async function createWorkspaceAction(
    _state: CreateWorkspaceState,
    formData: FormData,
  ): Promise<CreateWorkspaceState> {
    "use server";
    void _state;
    const rawName = formData.get("name");
    if (typeof rawName !== "string") return { error: "Enter an organisation name." };
    let input;
    try {
      input = workspaceCreationInput(rawName, crypto.randomUUID().replaceAll("-", "").slice(0, 8));
    } catch {
      return { error: "Enter an organisation name of up to 160 characters." };
    }
    const session = await getBrainSession();
    if (!session.user || !session.accessToken) redirect(demoAvailable() ? "/demo-signup" : "/sign-in");
    let organization;
    try {
      organization = await createOrganization(session.accessToken, input.name, input.slug);
    } catch (error) {
      if (error instanceof BrainApiError && error.status === 409) {
        return { error: "That workspace name is already in use. Please try again." };
      }
      return { error: "Brain could not create the workspace. Please try again shortly." };
    }
    redirect(`/?organizationId=${encodeURIComponent(organization.id)}`);
  }

  return (
    <ProductionWorkspace
      accessToken={accessToken}
      signedInName={signedInName}
      requestedOrganizationId={params.organizationId ?? null}
      requestedChannelId={params.channelId ?? null}
      requestedDirectMessageId={params.dmId ?? null}
      requestedMessageId={params.messageId ?? null}
      enableAskBrainBff
      enableEvidenceBff
      enableNativeChatBff
      enableDirectMessageBff
      enableActivityBff
      enableAgentWorkspaceBff
      enableLiveUpdatesBff
      enableWorkspaceSearchBff
      enableCollaborationPresenceBff
      demoSession={isDemo}
      signOutAction={signOutAction}
      createWorkspaceAction={createWorkspaceAction}
    />
  );
}
