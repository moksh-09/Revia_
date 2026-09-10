import { useState } from "react";
import type { TaskEntry, LineageState } from "../state/workspaceTypes";

interface RequestLineageProps {
  lineage: LineageState;
}

function formatSerial(n: number): string {
  return `REQUEST ${String(n).padStart(3, "0")}`;
}

function statusToStampClass(status: string): string {
  switch (status) {
    case "ACTIVE":       return "active";
    case "TOOL_RUNNING": return "working";
    case "GENERATING":   return "working";
    case "SPEAKING":     return "speaking";
    case "COMPLETED":    return "completed";
    case "OBSOLETE":
    case "CANCELLED":    return "obsolete";
    case "FAILED":       return "obsolete";
    default:             return "active";
  }
}

function statusToLabel(status: string): string {
  switch (status) {
    case "CREATED":      return "CREATED";
    case "ACTIVE":       return "ACTIVE";
    case "TOOL_RUNNING": return "TOOL RUNNING";
    case "GENERATING":   return "GENERATING";
    case "SPEAKING":     return "SPEAKING";
    case "COMPLETED":    return "COMPLETED";
    case "OBSOLETE":     return "REPLACED";
    case "CANCELLED":    return "CANCELLED";
    case "FAILED":       return "FAILED";
    default:             return status;
  }
}

function LineageTaskNode({ task, isCurrent }: { task: TaskEntry; isCurrent: boolean }) {
  const isObsolete = task.status === "OBSOLETE" || task.status === "CANCELLED" || task.status === "FAILED";

  return (
    <div
      className={`lineage-node ${isCurrent ? "lineage-node--current" : ""} ${isObsolete ? "lineage-node--obsolete" : ""}`}
      aria-label={`${formatSerial(task.serialNumber)}: ${task.requestText}, status: ${statusToLabel(task.status)}`}
    >
      <div className="lineage-node__serial">{formatSerial(task.serialNumber)}</div>
      <div className="lineage-node__text">"{task.requestText}"</div>
      <div className="lineage-node__stamps">
        <span className={`stamp stamp--${statusToStampClass(task.status)}`}>
          {statusToLabel(task.status)}
        </span>

        {task.toolName && (
          <span className="stamp stamp--working">
            TOOL: {task.toolName.replace(/_/g, " ").toUpperCase()}
          </span>
        )}

        {task.stoppedReason === "interrupted" && (
          <span className="stamp stamp--replaced">INTERRUPTED</span>
        )}

        {task.staleRejected && (
          <span className="stamp stamp--ignored">FENCE REJECTED · IGNORED ✓</span>
        )}

        {task.msSpoken !== undefined && task.msSpoken > 0 && (
          <span style={{
            fontFamily: "var(--font-mono)",
            fontSize: "8px",
            color: "var(--text-meta)",
            letterSpacing: "0.1em",
          }}>
            {(task.msSpoken / 1000).toFixed(1)}s spoken
          </span>
        )}
      </div>
    </div>
  );
}

export function RequestLineage({ lineage }: RequestLineageProps) {
  const [open, setOpen] = useState(false);
  const { tasks, interruptionDetectedAt } = lineage;

  const hasTasks = tasks.length > 0;
  const currentTask = [...tasks].reverse().find(
    (t) => t.status === "ACTIVE" || t.status === "TOOL_RUNNING" ||
           t.status === "GENERATING" || t.status === "SPEAKING"
  ) ?? tasks[tasks.length - 1] ?? null;

  const taskCount = tasks.length;

  return (
    <div className="lineage-drawer" aria-label="Request lineage">
      {/* Toggle */}
      <button
        className="lineage-toggle"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        aria-controls="lineage-content"
      >
        <span>
          Request Lineage
          {taskCount > 0 && (
            <span style={{ marginLeft: "10px", opacity: 0.6 }}>
              · {taskCount} {taskCount === 1 ? "request" : "requests"}
            </span>
          )}
        </span>
        <span className={`lineage-chevron ${open ? "lineage-chevron--open" : ""}`} aria-hidden="true">
          ↓
        </span>
      </button>

      {/* Content */}
      {open && (
        <div className="lineage-content" id="lineage-content">
          {!hasTasks ? (
            <p className="lineage-empty">No requests recorded yet. Start speaking to begin.</p>
          ) : (
            <>
              {tasks.map((task, i) => {
                const isCurrent = task.taskId === currentTask?.taskId;
                const isNotLast = i < tasks.length - 1;

                return (
                  <div key={task.taskId}>
                    <LineageTaskNode task={task} isCurrent={isCurrent} />

                    {/* Connector between tasks */}
                    {isNotLast && (
                      <div className="lineage-connector">
                        <span className="lineage-connector__arrow">↓</span>
                        {interruptionDetectedAt && i === tasks.length - 2 ? (
                          <span>USER INTERRUPTED</span>
                        ) : (
                          <span>SUPERSEDED BY</span>
                        )}
                      </div>
                    )}

                    {/* Stale result block — shows if this task finished late */}
                    {task.staleRejected && (
                      <>
                        <div className="lineage-connector">
                          <span className="lineage-connector__arrow">↓</span>
                          <span>LATE RESULT ARRIVED</span>
                        </div>
                        <div className="lineage-fence-block">
                          <div className="lineage-fence-block__label">
                            Fence Validation — {formatSerial(task.serialNumber)}
                          </div>
                          <div className="lineage-fence-block__row">
                            <span className="stamp stamp--replaced">AUTHORITY INVALID</span>
                            <span className="lineage-connector__arrow">→</span>
                            <span className="stamp stamp--ignored">RESULT IGNORED ✓</span>
                          </div>
                        </div>
                      </>
                    )}
                  </div>
                );
              })}
            </>
          )}
        </div>
      )}
    </div>
  );
}
