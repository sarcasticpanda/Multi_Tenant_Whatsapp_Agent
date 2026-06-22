import { useEffect, useRef } from "react";
import { STATUS } from "../tenants";
import { displayUrl } from "../api/client";

function renderText(text) {
  if (!text) return null;
  const parts = String(text).split(/(\*[^*\n]+\*|_[^_\n]+_)/g);
  return parts.map((p, i) => {
    if (p.startsWith("*") && p.endsWith("*")) return <strong key={i}>{p.slice(1, -1)}</strong>;
    if (p.startsWith("_") && p.endsWith("_")) return <em key={i}>{p.slice(1, -1)}</em>;
    return <span key={i}>{p}</span>;
  });
}

const fmtTime = (iso) =>
  iso ? new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "";

function Media({ msg }) {
  if (!msg.media_url) return null;
  if (msg.media_type === "IMAGE") {
    return (
      <a href={displayUrl(msg.media_url)} target="_blank" rel="noreferrer" className="block mt-1">
        <img src={displayUrl(msg.media_url)} alt="" className="rounded-lg max-w-[240px] border border-black/5" loading="lazy" />
      </a>
    );
  }
  if (msg.media_type === "DOCUMENT") {
    return (
      <a
        href={displayUrl(msg.media_url)}
        target="_blank"
        rel="noreferrer"
        className="flex items-center gap-2.5 mt-1 bg-black/[0.04] rounded-lg px-3 py-2.5 hover:bg-black/[0.07] transition-colors"
      >
        <span className="w-9 h-9 rounded-lg bg-alert/10 flex items-center justify-center shrink-0">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#C4543F" strokeWidth="1.6">
            <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" strokeLinejoin="round"/>
            <path d="M14 2v6h6" strokeLinejoin="round"/>
          </svg>
        </span>
        <div className="min-w-0">
          <div className="text-[13px] font-medium text-ink truncate">{msg.media_filename || "Document.pdf"}</div>
          <div className="text-[11px] text-muted">PDF · tap to open</div>
        </div>
      </a>
    );
  }
  return null;
}

export default function ChatThread({ session, messages }) {
  const endRef = useRef(null);
  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages, session]);

  if (!session) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center chat-canvas">
        <div className="w-16 h-16 rounded-2xl bg-white shadow-card flex items-center justify-center mb-4">
          <svg width="30" height="30" viewBox="0 0 24 24" fill="none" stroke="#2D5A4A" strokeWidth="1.5">
            <path d="M21 11.5a8.4 8.4 0 01-12 7.6L3 21l1.9-5.8A8.5 8.5 0 1121 11.5z" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
        </div>
        <p className="text-[14px] font-medium text-ink">Select a conversation</p>
        <p className="text-[12px] text-muted mt-1">Pick a customer on the left to audit the thread.</p>
      </div>
    );
  }

  const st = STATUS[session.status] || STATUS.WAITING_FOR_BOT;
  const needsHuman = session.status === "NEEDS_HUMAN";

  // Per-customer analytics derived from the thread
  const inbound = messages.filter((m) => m.direction === "INBOUND").length;
  const outbound = messages.filter((m) => m.direction === "OUTBOUND").length;
  const mediaSent = messages.filter((m) => m.direction === "OUTBOUND" && m.media_url).length;
  const fmtDate = (iso) => (iso ? new Date(iso).toLocaleDateString([], { day: "numeric", month: "short" }) : "—");
  const firstSeen = messages.length ? fmtDate(messages[0].timestamp) : "—";

  return (
    <div className="flex-1 flex flex-col min-h-0">
      {/* Thread header */}
      <div className="bg-chat-header text-white px-5 py-3 flex items-center gap-3 shrink-0">
        <div className="w-9 h-9 rounded-full bg-white/15 flex items-center justify-center font-mono text-[12px]">
          {String(session.customer_phone).slice(-2)}
        </div>
        <div className="flex-1 min-w-0">
          <div className="font-mono text-[14px] tracking-tight">{session.customer_phone}</div>
          <div className="text-[11.5px] text-white/70 flex items-center gap-1.5">
            <span className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: st.dot }} />
            {st.label}
          </div>
        </div>
        {needsHuman && (
          <span className="bg-alert text-white text-[11px] font-semibold px-2.5 py-1 rounded-full flex items-center gap-1.5">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2"><path d="M12 9v4M12 17h.01M10.3 3.9L1.8 18a2 2 0 001.7 3h17a2 2 0 001.7-3L14.4 3.9a2 2 0 00-3.4 0z" strokeLinecap="round" strokeLinejoin="round"/></svg>
            Human needed
          </span>
        )}
      </div>

      {/* Per-customer analytics strip */}
      <div className="bg-surface border-b border-hair px-5 py-2 flex items-center gap-5 text-[11.5px] shrink-0">
        <span className="text-muted">Customer received <b className="text-ink font-mono">{mediaSent}</b> file{mediaSent === 1 ? "" : "s"}</span>
        <span className="text-muted"><b className="text-ink font-mono">{inbound}</b> sent · <b className="text-ink font-mono">{outbound}</b> bot</span>
        <span className="text-muted">First seen <b className="text-ink">{firstSeen}</b></span>
        <span className="ml-auto inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10.5px] font-medium"
          style={{ backgroundColor: st.bg, color: st.text }}>
          <span className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: st.dot }} />{st.label}
        </span>
      </div>

      {/* Escalation banner */}
      {needsHuman && (
        <div className="bg-alert/8 border-b border-alert/20 px-5 py-2 text-[12px] text-alert font-medium">
          Auto-replies paused — this customer needs a human agent.
        </div>
      )}

      {/* Messages */}
      <div className="flex-1 overflow-y-auto chat-canvas px-5 py-4 space-y-1.5">
        {messages.map((m, i) => {
          const out = m.direction === "OUTBOUND";
          const prev = messages[i - 1];
          const grouped = prev && prev.direction === m.direction;
          return (
            <div key={m.message_id} className={`flex ${out ? "justify-end" : "justify-start"} ${grouped ? "mt-0.5" : "mt-2.5"}`}>
              <div
                className={`max-w-[68%] rounded-lg px-2.5 py-1.5 shadow-sm relative ${
                  out ? "bg-chat-out rounded-tr-sm" : "bg-chat-in rounded-tl-sm"
                }`}
              >
                {m.text_content && (
                  <div className="text-[13.5px] leading-[1.4] text-ink whitespace-pre-wrap break-words">
                    {renderText(m.text_content)}
                  </div>
                )}
                <Media msg={m} />
                <div className="flex items-center justify-end gap-1 mt-0.5 -mb-0.5">
                  {m.agent_state === "TYPING" && (
                    <span className="text-[9px] text-brand-deep/70 italic mr-auto">read · started typing</span>
                  )}
                  <span className="text-[10px] text-muted font-mono tabular">{fmtTime(m.timestamp)}</span>
                  {out && <span className="text-[11px] text-[#34B7F1] leading-none">✓✓</span>}
                </div>
              </div>
            </div>
          );
        })}

        {/* Live typing bubble */}
        {session.status === "AGENT_RESPONDING" && (
          <div className="flex justify-start mt-2.5">
            <div className="bg-chat-in rounded-lg rounded-tl-sm px-3 py-2.5 shadow-sm flex items-center gap-1.5">
              <span className="text-[12px] text-muted italic">typing</span>
              <span className="flex gap-1">
                {[0, 150, 300].map((d) => (
                  <span key={d} className="w-1.5 h-1.5 rounded-full bg-faint animate-pulsedot" style={{ animationDelay: `${d}ms` }} />
                ))}
              </span>
            </div>
          </div>
        )}
        <div ref={endRef} />
      </div>
    </div>
  );
}
