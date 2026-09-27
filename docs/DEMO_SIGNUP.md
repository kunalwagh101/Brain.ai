# Temporary test workspace on the real Brain API

Status: code verified locally; Render deployment and live multi-user acceptance pending.

This staging-only flow starts at `/demo-signup` when WorkOS is not set up. It creates a new real Brain `User`, isolated `Organization`, owner `Membership` and 12-hour revocable `DemoSession` in the backend database. The browser stores an HTTP-only cookie. Next.js reads that cookie on the server, verifies it with `/api/v1/auth/me`, and uses the bearer token server-side for the same `/api/brain` BFF routes as WorkOS. FastAPI still checks current membership for every channel, message, DM, evidence or admin request. `/demo` stays a separate read-only sample. No WorkOS token or password is fabricated.

## Render setup

1. Deploy the separate `brain-api-staging` and `brain-staging-db` services from `render.yaml`, with migration `20260927_0041` applied. Check that `https://<staging-api-host>/health/ready` returns 200. The blueprint runs in `BRAIN_ENVIRONMENT=staging`, enables `BRAIN_DEMO_SIGNUP_ENABLED=true`, generates `BRAIN_APP_SECRET`, and disables AWS instance metadata access. WorkOS and AWS provider credentials can be configured later; the demo channel flow does not need them. Keep this database isolated from production and customer data.
2. On the **existing frontend Render service** running `increment-10-ai-provider-gateway`, set `BRAIN_ENVIRONMENT=staging`, `BRAIN_DEMO_SIGNUP_ENABLED=true`, and `BRAIN_API_BASE_URL=https://<staging-api-host>` (the actual API origin, without a trailing path). Redeploy. WorkOS values may remain unset until the real sign-in is configured.
3. Visit `/`: it should lead to `/demo-signup`. Enter a name. The new account should open the real workspace, allow creating a channel and sending a message. Refresh and confirm the message persists. Sign out and confirm the same session cannot be used again. Use a separate browser session to verify a second tester cannot access the first organisation.

If `/setup` remains, the frontend opt-in or API URL is missing/invalid. If sign-up reports unavailable, inspect the staging API's health and env settings. If the workspace shows an error after sign-up, inspect the API and database logs. Do not silently switch the route to sample data.

The session expires after 12 hours; signing out revokes it earlier. A new signup creates a fresh empty organisation. **Session expiry does not delete stored test data.** Treat staging data as disposable, avoid personal/customer information, and clear the staging database under the operator's retention process. Successful signups are limited to five per client connection and 100 total in a rolling day. These limits are enforced in the database and may group testers behind one shared proxy.

Production rejects `BRAIN_DEMO_SIGNUP_ENABLED=true` at configuration validation, and the backend route also checks for staging at request time. The frontend requires an explicit staging flag and a valid API origin. When WorkOS is configured later, the existing AuthKit sign-in path remains in place; the activation template copying script must not be rerun over the already active product.

Local evidence: `AWS_EC2_METADATA_DISABLED=true /tmp/brain-demo-venv/bin/python -m pytest -q tests/test_demo_session.py tests/test_auth.py` verified signup, actual backend channel/message round trip, revocation, isolation and expiry. A local Next.js + FastAPI HTTP flow verified entry redirect, form submission, HTTP-only cookie, authenticated workspace, same-origin channel creation, message send and history. This is not Render acceptance.
