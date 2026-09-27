import Link from "next/link";
import { redirect } from "next/navigation";
import { demoAvailable, getBrainSession } from "../brain-session";
import styles from "./signup.module.css";

export const dynamic = "force-dynamic";

const errors: Record<string, string> = {
  name: "Enter a name of up to 80 characters.",
  limit: "Too many demo sign-ups right now. Try again later.",
  unavailable: "Brain could not start your workspace. Check the Brain API and try again.",
  origin: "Please submit this form from the Brain website.",
};

export default async function DemoSignup({
  searchParams,
}: {
  searchParams: Promise<{ error?: string; ended?: string }>;
}) {
  if (!demoAvailable()) redirect("/setup");
  const auth = await getBrainSession();
  if (auth.isDemo) redirect("/");
  const { error, ended } = await searchParams;

  return (
    <main className={styles.page}>
      <section className={styles.panel} aria-labelledby="demo-title">
        <Link className={styles.brand} href="/">✳ Brain</Link>
        <p className={styles.eyebrow}>TEMPORARY TEST WORKSPACE</p>
        <h1 id="demo-title">See how Brain works. Use real messages.</h1>
        <p>Enter a name to create your own workspace. Create a channel and send messages through the real Brain API. Your session ends after 12 hours. Test data stays in the staging database until it is cleared.</p>
        {ended && <p role="status" className={styles.status}>You have signed out of your demo workspace.</p>}
        {error && <p role="alert" className={styles.error}>{errors[error] ?? errors.unavailable}</p>}
        <form action="/demo-session" method="post">
          <label htmlFor="demo-name">Your name</label>
          <input id="demo-name" name="name" required minLength={1} maxLength={80} autoComplete="name" placeholder="For example, Kunal" />
          <button type="submit">Create my test workspace <span aria-hidden="true">→</span></button>
        </form>
        <p className={styles.note}>This workspace is for testing. Please do not add private or customer data. It is separate from WorkOS sign-in.</p>
        <Link href="/demo">Explore the read-only example</Link>
      </section>
    </main>
  );
}
