import { useState } from "react";
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
  if (s.length >= 12) return `+${s.slice(0, 2)} ${s.slice(2, 7)} ${s.slice(7)}`;
  return s;
}

const FILTERS = [
  { key: "all", label: "All" },
  { key: "AGENT_RESPONDING", label: "Active" },
  { key: "RESOLVED", label: "Resolved" },
  { key: "NEEDS_HUMAN", label: "Escalated" },
];

export default function ConversationList({ sessions, activeId, onSelect }) {
  const [filter, setFilter] = useState("all");
  const [q, setQ] = useState("");

  const counts = {
    all: sessions.length,
    AGENT_RESPONDING: sessions.filter((s) => s.status === "AGENT_RESPONDING").length,
    RESOLVED: sessions.filter((s) => s.status === "RESOLVED").length,
    NEEDS_HUMAN: sessions.filter((s) => s.status === "NEEDS_HUMAN").length,
  };

  const visible = sessions.filter((s) => {
    const okFilter = filter === "all" || s.status === filter;
    const okSearch = !q || String(s.customer_phone).includes(q.replace(/\D/g, ""));
    return okFilter && okSearch;
  });

  return (
    <div className="flex flex-col h-full">
      {/* Search + filters */}
      <div className="px-4 pt-3 pb-2 border-b border-hair space-y-2.5">
        <div className="relative">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#A99F92" strokeWidth="2"
            className="absolute left-2.5 top-1/2 -translate-y-1/2">
            <circle cx="11" cy="11" r="7" /><path d="M21 21l-4-4" strokeLinecap="round" />
          </svg>
          <input
            value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search by phone…"
            className="w-full text-[12.5px] pl-8 pr-2.5 py-1.5 rounded-lg bg-canvas border border-hair focus:outline-none focus:border-brand"
          />
        </div>
        <div className="flex gap-1">
          {FILTERS.map((f) => (
            <button
              key={f.key}
              onClick={() => setFilter(f.key)}
              className={`flex-1 text-[11px] font-medium py-1 rounded-md transition-colors ${
                filter === f.key ? "accent-bg text-white" : "bg-canvas text-muted hover:text-ink"
              }`}
            >
              {f.label}
              <span className={`ml-1 ${filter === f.key ? "text-white/80" : "text-faint"}`}>{counts[f.key] ?? 0}</span>
            </button>
          ))}
        </div>
      </div>

      {/* List */}
      <div className="flex-1 overflow-y-auto">
        {visible.length === 0 ? (
          <div className="px-5 py-10 text-center">
            <div className="w-12 h-12 rounded-2xl bg-canvas border border-hair mx-auto flex items-center justify-center mb-3">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#A99F92" strokeWidth="1.6">
                <path d="M21 11.5a8.4 8.4 0 01-12 7.6L3 21l1.9-5.8A8.5 8.5 0 1121 11.5z" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            </div>
            <p className="text-[13px] font-medium text-ink">{sessions.length === 0 ? "No conversations yet" : "No matches"}</p>
            <p className="text-[12px] text-faint mt-1">
              {sessions.length === 0 ? "Message the bot on WhatsApp to see it live." : "Try a different filter or search."}
            </p>
          </div>
        ) : (
          <ul>
            {visible.map((s) => {
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
                    <span className="self-stretch w-[3px] rounded-full -ml-1"
                      style={{ backgroundColor: needsHuman ? "#C4543F" : active ? "var(--tenant)" : "transparent" }} />
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
                        <span className="inline-flex items-center gap-1 text-[10.5px] font-medium px-1.5 py-0.5 rounded-full"
                          style={{ backgroundColor: st.bg, color: st.text }}>
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
        )}
      </div>
    </div>
  );
}
