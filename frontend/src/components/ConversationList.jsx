import { STATUS } from "../tenants";

function timeAgo(iso) {
  if (!iso) return "";
  const diff = (Date.now() - new Date(iso).getTime()) / 1000;
  if (diff < 60) return "now";
  if (diff < 3600) return `${Math.floor(diff / 60)}m`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h`;
  return `${Math.floor(diff / 86400)}d`;
}

function fmtPhone(p) {
  const s = String(p || "");
  // group as +CC XXXXX XXXXX for readability
  if (s.length >= 12) return `+${s.slice(0, 2)} ${s.slice(2, 7)} ${s.slice(7)}`;
  return s;
}

export default function ConversationList({ sessions, activeId, onSelect }) {
  if (!sessions.length) {
    return (
      <div className="px-5 py-10 text-center">
        <div className="w-12 h-12 rounded-2xl bg-canvas border border-hair mx-auto flex items-center justify-center mb-3">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#A99F92" strokeWidth="1.6">
            <path d="M21 11.5a8.4 8.4 0 01-12 7.6L3 21l1.9-5.8A8.5 8.5 0 1121 11.5z" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
        </div>
        <p className="text-[13px] font-medium text-ink">No conversations yet</p>
        <p className="text-[12px] text-faint mt-1">Message the bot on WhatsApp to see it appear here live.</p>
      </div>
    );
  }

  return (
    <ul>
      {sessions.map((s) => {
        const st = STATUS[s.status] || STATUS.WAITING_FOR_BOT;
        const active = activeId === s.session_id;
        const needsHuman = s.status === "NEEDS_HUMAN";
        const responding = s.status === "AGENT_RESPONDING";
        return (
          <li key={s.session_id}>
            <button
              onClick={() => onSelect(s)}
              className={`w-full text-left px-4 py-3 flex gap-3 items-center border-b border-hair/70 transition-colors ${
                active ? "bg-canvas" : "hover:bg-canvas/60"
              }`}
            >
              {/* accent edge for active / red for escalated */}
              <span
                className="self-stretch w-[3px] rounded-full -ml-1"
                style={{ backgroundColor: needsHuman ? "#E5484D" : active ? "var(--tenant)" : "transparent" }}
              />
              <div className="relative w-10 h-10 rounded-full bg-ink/90 text-white flex items-center justify-center shrink-0">
                <span className="font-mono text-[12px]">{String(s.customer_phone).slice(-2)}</span>
                {responding && (
                  <span className="absolute -bottom-0.5 -right-0.5 w-3 h-3 rounded-full bg-brand border-2 border-surface animate-pulsedot" />
                )}
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between gap-2">
                  <span className="font-mono text-[13px] text-ink truncate">{fmtPhone(s.customer_phone)}</span>
                  <span className="text-[11px] text-faint font-mono shrink-0">{timeAgo(s.last_message_at)}</span>
                </div>
                <div className="flex items-center gap-2 mt-1">
                  <span
                    className="inline-flex items-center gap-1 text-[10.5px] font-medium px-1.5 py-0.5 rounded-full"
                    style={{ backgroundColor: st.bg, color: st.text }}
                  >
                    <span className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: st.dot }} />
                    {st.label}
                  </span>
                  <span className="text-[11px] text-faint">{s.message_count || 0} msgs</span>
                </div>
              </div>
            </button>
          </li>
        );
      })}
    </ul>
  );
}
