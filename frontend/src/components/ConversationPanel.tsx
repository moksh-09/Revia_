import type { ConversationMessage } from "../state/workspaceTypes";

export function ConversationPanel({ messages }: { messages: ConversationMessage[] }) {
  return (
    <section className="panel conversation-panel" aria-labelledby="conversation-title">
      <div className="panel-heading">
        <div>
          <span className="eyebrow">LIVE CONVERSATION</span>
          <h2 id="conversation-title">Your conversation</h2>
        </div>
        <span className="message-count">{messages.length} messages</span>
      </div>
      <div className="conversation-list">
        {messages.map((message) => (
          <article className={`message message-${message.role}`} key={message.id}>
            <div className="message-meta">
              <span>{message.role === "assistant" ? "REVIA" : "YOU"}</span>
              <time>{message.timeLabel}</time>
            </div>
            <p>{message.text}</p>
          </article>
        ))}
        <div className="transcript-placeholder" aria-live="polite">
          <span className="transcript-dot" />
          {"Live transcript will appear here when your session is connected."}
        </div>
      </div>
    </section>
  );
}
