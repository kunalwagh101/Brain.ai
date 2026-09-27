import { WorkOS } from "@workos-inc/node";

// Real, isolated WorkOS staging identities. No frontend auth bypass and no
// committed or shared password. Run locally with operator-supplied passwords.
const apiKey = process.env.WORKOS_API_KEY;
if (!apiKey?.startsWith("sk_test_")) {
  console.error("A staging WorkOS API key (sk_test_) is required. No accounts created.");
  process.exit(1);
}
if (process.env.BRAIN_DEMO_PROVISION !== "1") {
  console.error("Set BRAIN_DEMO_PROVISION=1 to explicitly enable staging test-user creation.");
  process.exit(1);
}

const accounts = [
  { email: "brain-demo-owner@example.com", password: process.env.BRAIN_DEMO_OWNER_PASSWORD, firstName: "Demo", lastName: "Owner", marker: "owner" },
  { email: "brain-demo-member@example.com", password: process.env.BRAIN_DEMO_MEMBER_PASSWORD, firstName: "Demo", lastName: "Member", marker: "member" },
];
if (accounts.some((account) => !account.password || account.password.length < 16)) {
  console.error("Set both BRAIN_DEMO_OWNER_PASSWORD and BRAIN_DEMO_MEMBER_PASSWORD to distinct passwords of at least 16 characters. No accounts created.");
  process.exit(1);
}
if (accounts[0].password === accounts[1].password) {
  console.error("Staging test users must have different passwords. No accounts created.");
  process.exit(1);
}

const workos = new WorkOS(apiKey);
try {
  const existingUsers = new Map();
  // Check both before writes so an unrelated existing account cannot be reused.
  for (const account of accounts) {
    const existing = await workos.userManagement.listUsers({ email: account.email });
    const user = existing.data.find((candidate) => candidate.email.toLowerCase() === account.email);
    if (user && user.metadata?.brain_demo_account !== account.marker)
      throw new Error(`Account ${account.email} already exists but was not created by this staging setup. No changes made.`);
    if (user) existingUsers.set(account.email, user);
  }
  for (const { email, password, firstName, lastName, marker } of accounts) {
    if (existingUsers.has(email)) {
      console.log(`Already exists: ${email}. Password unchanged; use the original password.`);
      continue;
    }
    const user = await workos.userManagement.createUser({
      email, password, firstName, lastName, emailVerified: true,
      metadata: { brain_demo_account: marker },
    });
    console.log(`Created WorkOS staging test user ${email}: ${user.id}`);
  }
  console.log("Sign in as the owner and create a Brain organisation. Then sign in as the member once and add that address in Brain Admin. No passwords were printed or saved.");
} catch (error) {
  if (error instanceof Error && error.message.startsWith("Account ")) console.error(error.message);
  else console.error("Staging user creation failed. Inspect your WorkOS staging dashboard before retrying; one user may already exist.");
  process.exitCode = 1;
}
