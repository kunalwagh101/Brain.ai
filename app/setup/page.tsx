import Link from "next/link";
import { redirect } from "next/navigation";
import { configurationIssues, demoModeReady } from "../workspace-configuration";
import styles from "./setup.module.css";

export const dynamic = "force-dynamic";

export default function SetupRequired() {
  const issues = configurationIssues(process.env, process.env.NODE_ENV === "production");
  if (!issues.length || demoModeReady(process.env, process.env.NODE_ENV === "production")) redirect("/");

  return (
    <main className={styles.page}>
      <section className={styles.panel} aria-labelledby="setup-title">
        <div className={styles.identity}><span className={styles.symbol} aria-hidden="true">✳</span> Brain <span className={styles.label}>Deployment setup</span></div>
        <p className={styles.eyebrow}>ACTION REQUIRED · SIGN-IN UNAVAILABLE</p>
        <h1 id="setup-title">Your workspace is waiting for its connection.</h1>
        <p className={styles.intro}>This deployment cannot reach sign-in yet. To use a temporary test account, deploy the Brain API and enable staging demo sign-up on both services. Or add the WorkOS settings below for real accounts. No user is signed in.</p>
        <div className={styles.settings}>
          <h2>Missing or invalid settings</h2>
          <ul>{issues.map((issue) => <li key={issue}><code>{issue}</code></li>)}</ul>
          <p>Values are never shown here. Use your own WorkOS staging application and the HTTPS URL of your Brain API.</p>
        </div>
        <p className={styles.instructions}>The backend also needs <code>BRAIN_WORKOS_CLIENT_ID</code> and the WorkOS JWT email claim. Follow the <a href="https://github.com/kunalwagh101/Brain.ai/blob/increment-10-ai-provider-gateway/docs/WORKOS_FRONTEND_ACCEPTANCE.md">setup instructions</a> for the callback URL and sign-in settings.</p>
        <p className={styles.instructions}>Temporary test sign-up needs an HTTPS <code>BRAIN_API_BASE_URL</code>, plus <code>BRAIN_ENVIRONMENT=staging</code> and <code>BRAIN_DEMO_SIGNUP_ENABLED=true</code> on the frontend. The API service must also run in staging with demo sign-up enabled. <a href="https://github.com/kunalwagh101/Brain.ai/blob/increment-10-ai-provider-gateway/docs/DEMO_SIGNUP.md">Demo setup guide</a>.</p>
        <div className={styles.footer}><Link href="/demo">Explore the read-only example</Link><span>Example data cannot send real messages.</span></div>
      </section>
    </main>
  );
}
