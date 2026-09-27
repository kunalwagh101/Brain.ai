"use client";

import styles from "./workspace-error.module.css";

export default function WorkspaceError({ reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return (
    <main className={styles.page} role="alert">
      <section className={styles.panel}>
        <span className={styles.brand}>✳ Brain</span>
        <p className={styles.eyebrow}>WORKSPACE UNAVAILABLE</p>
        <h1>We couldn’t load your workspace.</h1>
        <p>Your sign-in may be fine, but Brain could not finish loading your organisation data. Try again. If it keeps happening, check that the Brain API and database are running.</p>
        <button onClick={reset}>Try again</button>
      </section>
    </main>
  );
}
