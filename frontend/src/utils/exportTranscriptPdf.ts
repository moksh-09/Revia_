import { jsPDF } from "jspdf";
import type { WorkspaceState } from "../state/workspaceTypes";

/**
 * Generate and download a formatted PDF transcript of the REVIA voice session.
 */
export function exportTranscriptPdf(state: WorkspaceState): void {
  const doc = new jsPDF({
    orientation: "portrait",
    unit: "mm",
    format: "a4",
  });

  const pageWidth = doc.internal.pageSize.getWidth();
  const margin = 16;
  const contentWidth = pageWidth - margin * 2;
  let y = margin;

  // ── Header Bar ──────────────────────────────────────────────────────────
  doc.setFillColor(184, 41, 47); // REVIA Crimson #B8292F
  doc.rect(margin, y, contentWidth, 2, "F");
  y += 7;

  // Brand title
  doc.setFont("helvetica", "bold");
  doc.setFontSize(18);
  doc.setTextColor(26, 26, 26);
  doc.text("REVIA", margin, y);

  doc.setFont("helvetica", "normal");
  doc.setFontSize(9);
  doc.setTextColor(110, 110, 110);
  doc.text("Voice Intelligence Dossier · Session Transcript", margin + 24, y - 1);
  y += 6;

  // Tagline
  doc.setFontSize(8);
  doc.setTextColor(140, 140, 140);
  doc.text("Interruptible by design · Correct by construction", margin, y);
  y += 7;

  // Divider
  doc.setDrawColor(220, 220, 220);
  doc.setLineWidth(0.3);
  doc.line(margin, y, margin + contentWidth, y);
  y += 6;

  // ── Session Metadata Card ───────────────────────────────────────────────
  doc.setFillColor(248, 248, 248);
  doc.rect(margin, y, contentWidth, 24, "F");
  doc.setDrawColor(230, 230, 230);
  doc.rect(margin, y, contentWidth, 24, "S");

  doc.setFontSize(8);
  doc.setFont("helvetica", "bold");
  doc.setTextColor(90, 90, 90);

  const col1 = margin + 4;
  const col2 = margin + 50;
  const col3 = margin + 105;
  const col4 = margin + 145;

  // Row 1
  doc.text("SESSION ID:", col1, y + 6);
  doc.text("AUDIO PROFILE:", col2, y + 6);
  doc.text("VOICE IDENTITY:", col3, y + 6);
  doc.text("TOTAL TURNS:", col4, y + 6);

  doc.setFont("helvetica", "normal");
  doc.setTextColor(30, 30, 30);
  doc.text(state.sessionId || "revia-active-session", col1, y + 10);
  doc.text(
    state.voiceConfig.telephonyMode
      ? "Telephony (8kHz Narrowband)"
      : "Studio HD (16kHz PCM)",
    col2,
    y + 10
  );
  doc.text(
    `Rime ${state.rime.model.toUpperCase()} · ${state.rime.voice.toUpperCase()} (${state.voiceConfig.speedAlpha}x)`,
    col3,
    y + 10
  );
  doc.text(`${state.messages.length}`, col4, y + 10);

  // Row 2
  doc.setFont("helvetica", "bold");
  doc.setTextColor(90, 90, 90);
  doc.text("EXPORTED AT:", col1, y + 17);
  doc.text("LANGUAGE:", col2, y + 17);
  doc.text("PERSONA PRESET:", col3, y + 17);
  doc.text("TASKS CREATED:", col4, y + 17);

  doc.setFont("helvetica", "normal");
  doc.setTextColor(30, 30, 30);
  doc.text(new Date().toLocaleString(), col1, y + 21);
  doc.text(state.voiceConfig.language.toUpperCase(), col2, y + 21);
  doc.text(state.voiceConfig.persona.toUpperCase(), col3, y + 21);
  doc.text(`${state.lineage.tasks.length}`, col4, y + 21);

  y += 30;

  // ── Conversation Transcript Section ─────────────────────────────────────
  doc.setFont("helvetica", "bold");
  doc.setFontSize(11);
  doc.setTextColor(184, 41, 47);
  doc.text("CONVERSATION TRANSCRIPT", margin, y);
  y += 5;

  if (state.messages.length === 0) {
    doc.setFont("helvetica", "italic");
    doc.setFontSize(9);
    doc.setTextColor(140, 140, 140);
    doc.text("No dialogue recorded in this session.", margin, y + 5);
    y += 12;
  } else {
    for (const msg of state.messages) {
      // Check page overflow
      if (y > 265) {
        doc.addPage();
        y = margin;
      }

      const isUser = msg.role === "user";
      doc.setFont("helvetica", "bold");
      doc.setFontSize(8);

      if (isUser) {
        doc.setTextColor(50, 50, 50);
        doc.text(`YOU [${msg.timeLabel || "Turn"}]`, margin, y);
      } else {
        doc.setTextColor(184, 41, 47);
        doc.text(`REVIA [${msg.timeLabel || "Turn"}]`, margin, y);
      }

      y += 4;

      doc.setFont("helvetica", "normal");
      doc.setFontSize(9);
      doc.setTextColor(20, 20, 20);

      const splitText = doc.splitTextToSize(msg.text, contentWidth - 6);
      doc.text(splitText, margin + 2, y);
      y += splitText.length * 4.5 + 4;
    }
  }

  y += 4;

  // ── Task Lineage & Authority Audit ──────────────────────────────────────
  if (y > 230) {
    doc.addPage();
    y = margin;
  }

  doc.setFont("helvetica", "bold");
  doc.setFontSize(11);
  doc.setTextColor(184, 41, 47);
  doc.text("REQUEST LINEAGE & AUTHORITY AUDIT", margin, y);
  y += 6;

  // Table header
  doc.setFillColor(240, 240, 240);
  doc.rect(margin, y, contentWidth, 6, "F");
  doc.setFontSize(7.5);
  doc.setFont("helvetica", "bold");
  doc.setTextColor(80, 80, 80);

  doc.text("#", margin + 2, y + 4.2);
  doc.text("TASK ID", margin + 10, y + 4.2);
  doc.text("REQUEST", margin + 35, y + 4.2);
  doc.text("TOOL RUN", margin + 110, y + 4.2);
  doc.text("STATUS", margin + 140, y + 4.2);
  doc.text("SPOKEN", margin + 165, y + 4.2);

  y += 7;

  if (state.lineage.tasks.length === 0) {
    doc.setFont("helvetica", "italic");
    doc.setFontSize(8.5);
    doc.setTextColor(140, 140, 140);
    doc.text("No tasks generated in this session.", margin + 2, y + 4);
    y += 10;
  } else {
    doc.setFont("helvetica", "normal");
    doc.setFontSize(7.5);

    for (const t of state.lineage.tasks) {
      if (y > 270) {
        doc.addPage();
        y = margin;
      }

      doc.setTextColor(40, 40, 40);
      doc.text(String(t.serialNumber).padStart(3, "0"), margin + 2, y + 4);
      doc.text(t.taskId.slice(0, 12), margin + 10, y + 4);

      const reqSummary = t.requestText.length > 40 ? t.requestText.slice(0, 38) + "…" : t.requestText;
      doc.text(reqSummary, margin + 35, y + 4);
      doc.text(t.toolName || "—", margin + 110, y + 4);

      // Status color
      if (t.status === "COMPLETED") {
        doc.setTextColor(26, 122, 58);
      } else if (t.status === "OBSOLETE" || t.status === "CANCELLED") {
        doc.setTextColor(184, 41, 47);
      } else {
        doc.setTextColor(80, 80, 80);
      }
      doc.text(t.status, margin + 140, y + 4);

      doc.setTextColor(50, 50, 50);
      const spokenText = t.msSpoken !== undefined ? `${(t.msSpoken / 1000).toFixed(1)}s` : "—";
      doc.text(spokenText, margin + 165, y + 4);

      y += 6;
    }
  }

  // ── Footer ──────────────────────────────────────────────────────────────
  const totalPages = (doc as any).internal.getNumberOfPages();
  for (let i = 1; i <= totalPages; i++) {
    doc.setPage(i);
    doc.setFont("helvetica", "normal");
    doc.setFontSize(7);
    doc.setTextColor(150, 150, 150);
    doc.text(
      "REVIA Voice Intelligence · DataForge x Rime Hackathon Challenge · Powered by Rime TTS & LiveKit",
      margin,
      290
    );
    doc.text(`Page ${i} of ${totalPages}`, pageWidth - margin - 15, 290);
  }

  // Trigger download
  const filename = `revia-dossier-${state.sessionId || "session"}-${new Date().toISOString().slice(0, 10)}.pdf`;
  doc.save(filename);
}
