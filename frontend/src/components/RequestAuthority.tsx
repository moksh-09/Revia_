import type { WorkspaceState } from "../state/workspaceTypes";

interface RequestAuthorityProps {
  state: WorkspaceState;
}

function formatSerial(n: number): string {
  return `REQUEST / ${String(n).padStart(3, "0")}`;
}

export function RequestAuthority({ state }: RequestAuthorityProps) {
  const { lineage, voiceState } = state;
  const tasks = lineage.tasks;

  // Current task = last non-terminal or last task
  const currentTask = [...tasks].reverse().find(
    (t) => t.status === "ACTIVE" || t.status === "TOOL_RUNNING" ||
           t.status === "GENERATING" || t.status === "SPEAKING"
  ) ?? tasks[tasks.length - 1] ?? null;

  // Previous task = task before current
  const previousTask = currentTask
    ? tasks.filter((t) => t.taskId !== currentTask.taskId).slice(-1)[0] ?? null
    : null;

  // Determine authority labels
  const currentAuthority = "CURRENT";
  const previousAuthority = "OBSOLETE";

  const currentStatusLabel =
    currentTask?.status === "TOOL_RUNNING" ? "WORKING" :
    currentTask?.status === "GENERATING"   ? "THINKING" :
    currentTask?.status === "SPEAKING"     ? "SPEAKING" :
    currentTask?.status === "ACTIVE"       ? "ACTIVE" :
    currentTask?.status === "COMPLETED"    ? "COMPLETED" :
    currentTask?.status === "OBSOLETE"     ? "REPLACED" :
    currentTask?.status === "CANCELLED"    ? "CANCELLED" :
    currentTask?.status === "FAILED"       ? "FAILED" :
    "ACTIVE";

  const hasLiveTask = currentTask && (
    currentTask.status === "ACTIVE" ||
    currentTask.status === "TOOL_RUNNING" ||
    currentTask.status === "GENERATING" ||
    currentTask.status === "SPEAKING"
  );

  return (
    <section className="sheet" aria-labelledby="request-authority-title">
      <div className="sheet-header">
        <div>
          <span className="sheet-eyebrow">Task Authority</span>
          <h2 className="sheet-title" id="request-authority-title">Request Status</h2>
        </div>
        {hasLiveTask && (
          <span className="stamp stamp--active" aria-label="Current request is active">
            ● LIVE
          </span>
        )}
      </div>

      <div className="request-authority">
        {/* Current request */}
        <div className="request-block request-block--current" aria-label="Current request">
          <div className="request-block__label">
            <span>{currentTask ? formatSerial(currentTask.serialNumber) : "REQUEST / —"}</span>
            <span className={`stamp stamp--${
              currentTask?.status === "TOOL_RUNNING" ? "working" :
              currentTask?.status === "SPEAKING"     ? "speaking" :
              currentTask?.status === "GENERATING"   ? "working" :
              "active"
            }`}>
              {currentStatusLabel}
            </span>
          </div>

          <p className="request-block__text">
            {currentTask?.requestText ?? (
              voiceState === "idle"
                ? "Awaiting first request"
                : "Processing..."
            )}
          </p>

          <div className="request-meta-row">
            <div className="request-meta-item">
              <span className="request-meta-item__key">Status</span>
              <span className="request-meta-item__val request-meta-item__val--crimson">
                {currentStatusLabel}
              </span>
            </div>
            <div className="request-meta-item">
              <span className="request-meta-item__key">Authority</span>
              <span className="request-meta-item__val request-meta-item__val--crimson">
                {currentAuthority}
              </span>
            </div>
            {currentTask?.toolName && (
              <div className="request-meta-item">
                <span className="request-meta-item__key">Tool</span>
                <span className="request-meta-item__val">{currentTask.toolName}</span>
              </div>
            )}
          </div>
        </div>

        {/* Previous request — only shown when there's a history */}
        {previousTask && (
          <div className="request-block request-block--previous" aria-label="Previous request (replaced)">
            <div className="request-block__label">
              <span>{formatSerial(previousTask.serialNumber)}</span>
              <span className="stamp stamp--replaced">REPLACED</span>
            </div>

            <p className="request-block__text">{previousTask.requestText}</p>

            <div className="request-meta-row">
              <div className="request-meta-item">
                <span className="request-meta-item__key">Status</span>
                <span className="request-meta-item__val request-meta-item__val--dim">
                  {previousTask.status}
                </span>
              </div>
              <div className="request-meta-item">
                <span className="request-meta-item__key">Authority</span>
                <span className="request-meta-item__val request-meta-item__val--dim">
                  {previousAuthority}
                </span>
              </div>
              {previousTask.staleRejected && (
                <div className="request-meta-item">
                  <span className="request-meta-item__key">Result</span>
                  <span className="request-meta-item__val">
                    <span className="stamp stamp--ignored">IGNORED ✓</span>
                  </span>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </section>
  );
}
