"use client";

import { useActionState } from "react";
import styles from "./create-workspace-form.module.css";

export type CreateWorkspaceState = { error: string | null };

export function CreateWorkspaceForm({
  action,
}: {
  action: (state: CreateWorkspaceState, data: FormData) => Promise<CreateWorkspaceState>;
}) {
  const [state, formAction, pending] = useActionState(action, { error: null });

  return (
    <form className={styles.form} action={formAction}>
      <label htmlFor="workspace-name">Organisation name</label>
      <input id="workspace-name" name="name" type="text" minLength={1} maxLength={160} required autoComplete="organization" placeholder="e.g. My team" aria-describedby={state.error ? "workspace-error" : undefined} aria-invalid={Boolean(state.error)} />
      {state.error && <p id="workspace-error" role="alert">{state.error}</p>}
      <button type="submit" disabled={pending}>{pending ? "Creating…" : "Create workspace"}</button>
    </form>
  );
}
