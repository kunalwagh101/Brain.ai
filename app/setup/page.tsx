export default function SetupRequired() {
  return (
    <main style={{ maxWidth: 590, margin: "12vh auto", padding: "24px", fontFamily: "system-ui, sans-serif", lineHeight: 1.6 }}>
      <p style={{ color: "#236a69", fontWeight: 700 }}>Brain workspace</p>
      <h1>Sign-in is not configured yet</h1>
      <p>The production workspace needs WorkOS and the Brain API before anyone can sign in or send messages. No sample account has been signed in.</p>
      <p>If you manage this deployment, set the frontend WorkOS and Brain API environment variables in Render, then redeploy. The exact names and WorkOS dashboard settings are in <code>docs/WORKOS_FRONTEND_ACCEPTANCE.md</code>.</p>
      <a href="/demo">View the separate read-only example</a>
    </main>
  );
}
