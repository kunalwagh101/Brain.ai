# Brain workspace redesign

## Product alignment

The root route shows a **read-only sample** until official WorkOS activation. Its data enters the same `WorkspaceShell`, `NativeChatPanel`, `DirectMessagePanel`, `ActivityPanel`, project and memory views, `EvidenceWorkspace`, `AgentWorkspacePanel`, and `AdminCenterPanel` used by `ProductionWorkspace`. The sample has no mutation endpoints or credentials. WorkOS activation replaces the root page with authenticated `ProductionWorkspace`; `/demo` remains the explicit sample route.

| Existing capability | Screen | Boundary retained |
| --- | --- | --- |
| Teams, groups, channels, unread counts, pins, threads, reactions, attachments | Channels | Server-filtered membership; channel mutations through same-origin BFF only |
| Participant-only DMs | Direct messages | Outside organisation-wide search, memory, and executive surfaces |
| Mentions, replies, agents, project updates, integration failures | Activity | References to source objects; notification preferences and read mutations through BFF |
| Saved messages | Saved | Per-user saved state |
| Connected tracks and structured projects | Tracks / Projects | Permission-filtered read models and evidence provenance |
| Confirmed blockers and decisions | Decisions & blockers | Confidence and canonical event links retained |
| Evidence and documents | Files & evidence | Upload/delete available only after authenticated BFF activation |
| Governed answers, agent runs, model and tool policies | Ask Brain / Developer & agents | Runtime and mutation gates remain server-controlled |
| Membership, integrations, model providers, API grants | Admin & governance | Screen only appears when an admin read model is provided |

The prior long scrolling page exposed every tool at once. The new shell keeps a narrow global rail, a contextual team/channel sidebar, and one focused work surface. Activity is a proper screen; threads remain a contextual panel inside a conversation. Desktop gives the conversation room to breathe. Mobile offers a scrollable workspace browser with actual channel and DM links; it closes after navigation. Existing `#native-chat`, `#direct-messages`, `#activity-center`, `#project-*`, `#track-*`, `#saved-messages`, and other hashes still select their corresponding view.

## Visual system

| Token | Value | Purpose |
| --- | --- | --- |
| Navigation navy | `#222d40` | Distinct, stable location cues |
| Canvas | `#f8f9f6` | Low glare while reading long conversations |
| Surface | `#ffffff` | Clear separation for working areas |
| Text | `#253247` | Strong contrast for information |
| Muted text | `#667386` | Secondary labels without competing with content |
| Action teal | `#236a69` | Clear action and active state |
| Brand warmth | `#e1b890` | Reserved for the mark and active rail indicator |
| Dividers | `#e7e8e5` | Structure without stacked glowing cards |

The shell uses a 62px rail, 256px sidebar, and flexible canvas; narrow widths collapse the sidebar into `Browse workspace`. Working copy and conversation bodies have larger type, while timestamps and provenance remain quieter. Focus rings, skip navigation, semantic sections, `aria-current`, reduced-motion support, and visible empty states remain intact.

## Component usage and states

`ProductionWorkspace` loads permission-filtered data and passes it to `WorkspaceShell`. Before authentication is configured, `/demo` supplies labelled example data to the same shell with `demoMode`; it cannot post or upload. The shell's `MobileWorkspaceNavigation` wraps a native disclosure, so its links work with keyboard before hydration and the disclosure closes after a selection. `WorkspaceHeading` receives focus when the active screen changes. A channel thread returns focus to its parent reply control on close.

```tsx
<MobileWorkspaceNavigation className={styles.mobileNavigation}>
  <summary>Browse workspace</summary>
  <nav aria-label="Mobile workspace navigation">
    <a href="#activity-center">Activity</a>
  </nav>
</MobileWorkspaceNavigation>
```

States to check with actual accounts: no visible channels, archived/revoked channel, no DM or a revoked participant, empty and failed Activity/Search, unknown project progress, no evidence for Ask Brain, role-denied Admin, pending agent approval, mobile browser open/closed and keyboard focus after a thread closes. Search only shows a remote excerpt for the exact query and endpoint that returned it. Permission decisions still come from the server; search results must be rechecked after real access revocation.

## Reference decisions

- [Slack's sidebar](https://slack.com/help/articles/212596808-Adjust-your-sidebar-preferences) separates Home, Activity, and Later alongside channels and DMs. Its [Activity view](https://slack.com/help/articles/46751260742035-Introducing-the-new-Activity-view-in-Slack) emphasises a single place to take action. Brain adds governance and evidence as first-class, permission-aware destinations.
- [Discord's Inbox](https://support.discord.com/hc/en-us/articles/360045027712-Inbox-FAQ) and [threads](https://support.discord.com/hc/en-us/articles/4403205878423-Threads-FAQ) informed the grouped navigation, badges, and contextual thread. Brain retains a quieter reading canvas suitable for work and audit trails.
- For repeatable public competitor research, [Scrapling](https://scrapling.readthedocs.io/en/latest/) is appropriate for a small set of dynamic pages and DOM extraction; [Crawl4AI](https://docs.crawl4ai.com/core/quickstart/) suits a broader documentation crawl into readable Markdown; [Playwright](https://playwright.dev/docs/intro) suits interaction and responsive visual checks. First-party help documentation was used for this implementation. No logged-in competitor account was scraped, and no scraper library was added to the product bundle.

## Verification and known gates

Run `npm run build` and `node --test tests/*.test.mjs`. The route test checks that old deep links reveal the correct feature; the rendered HTML test checks sample labelling and the shared feature structure. The read-only demo does not claim that WorkOS activation, live API credentials, external integrations, or UAT have been completed. Keep the existing story board gates until those checks are performed in an authenticated environment.
