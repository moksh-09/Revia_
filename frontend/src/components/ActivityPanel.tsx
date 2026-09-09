import type { ActivityState } from "../state/workspaceTypes";

export function ActivityPanel({ activity }: { activity: ActivityState }) {
  return (
    <section className="panel activity-panel" aria-labelledby="activity-title">
      <div className="panel-heading compact">
        <div>
          <span className="eyebrow">CURRENT ACTIVITY</span>
          <h2 id="activity-title">Request context</h2>
        </div>
        <span className={`status-pill status-${activity.status}`}>{activity.status}</span>
      </div>
      <div className="activity-body">
        <div className="activity-row featured">
          <span>Current request</span>
          <strong>{activity.currentRequest ?? "No active request"}</strong>
        </div>
        <div className="activity-row">
          <span>Current work</span>
          <strong>{activity.currentWork ?? "Standing by"}</strong>
        </div>
        <div className="activity-row">
          <span>Previous request</span>
          <strong>{activity.previousRequest ?? "None"}</strong>
        </div>
      </div>
    </section>
  );
}
