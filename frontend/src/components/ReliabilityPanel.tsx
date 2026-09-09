import type { ReliabilityState } from "../state/workspaceTypes";

export function ReliabilityPanel({ reliability }: { reliability: ReliabilityState }) {
  return (
    <section className="panel reliability-panel" aria-labelledby="reliability-title">
      <div className="panel-heading compact">
        <div>
          <span className="eyebrow">RELIABILITY</span>
          <h2 id="reliability-title">Request lineage</h2>
        </div>
        <span className="shield-mark" aria-hidden="true">✓</span>
      </div>
      <div className="lineage">
        <div className="lineage-node lineage-previous">
          <span className="lineage-label">Previous request</span>
          <strong>{reliability.replacedRequest ?? "No replaced request"}</strong>
          <span className="lineage-state">Replaced</span>
        </div>
        <div className="lineage-connector" aria-hidden="true">↓</div>
        <div className="lineage-node lineage-current">
          <span className="lineage-label">Current request</span>
          <strong>{reliability.currentRequest ?? "No active request"}</strong>
          <span className="lineage-state">Active</span>
        </div>
      </div>
      <div className={`reliability-note ${reliability.staleResultIgnored ? "is-confirmed" : ""}`}>
        <span aria-hidden="true">{reliability.staleResultIgnored ? "✓" : "·"}</span>
        <span>{reliability.staleResultIgnored ? "Older result ignored safely" : "Waiting for live authority state"}</span>
      </div>
    </section>
  );
}
