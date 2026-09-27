"use client";

import type { ActivitySummary } from "./activity-api";
import { ActivityPanel } from "./activity-panel";
import styles from "./activity-dock.module.css";

export function ActivityDock({
  activity,
  organizationId,
  mutationBase,
}: {
  activity: ActivitySummary;
  organizationId: string;
  mutationBase: string | null;
}) {
  return (
    <details className={styles.dock} id="activity-center">
      <summary aria-label={`Activity, ${activity.unread_count} unread`}>
        <span aria-hidden="true">☰</span>
        <span>Activity</span>
        {activity.unread_count ? (
          <b>{activity.unread_count > 99 ? "99+" : activity.unread_count}</b>
        ) : null}
      </summary>
      <div className={styles.drawer}>
        <ActivityPanel
          activity={activity}
          organizationId={organizationId}
          mutationBase={mutationBase}
        />
      </div>
    </details>
  );
}
