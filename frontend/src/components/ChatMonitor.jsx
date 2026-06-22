const STATUS_STYLES = {
  WAITING_FOR_BOT: "bg-gray-100 text-gray-600",
  AGENT_RESPONDING: "bg-blue-100 text-blue-700 animate-pulse",
  RESOLVED: "bg-green-100 text-green-700",
  NEEDS_HUMAN: "bg-red-100 text-red-700",
};

const STATUS_LABEL = {
  WAITING_FOR_BOT: "Waiting",
  AGENT_RESPONDING: "Bot typing…",
  RESOLVED: "Resolved",
  NEEDS_HUMAN: "Needs human",
};

function timeAgo(iso) {
  if (!iso) return "";
  const diff = (Date.now() - new Date(iso).getTime()) / 1000;
  if (diff < 60) return "just now";
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}

export default function ChatMonitor({ sessions, activeSession, onSelect }) {
  if (!sessions.length) {
    return (
      <div className="p-6 text-center text-gray-400 text-sm">
        No conversations yet.<br />
        Send a WhatsApp message to the bot to see it here.
      </div>
    );
  }

  return (
    <div className="divide-y divide-gray-100">
      {sessions.map((s) => {
        const active = activeSession === s.session_id;
        const needsHuman = s.status === "NEEDS_HUMAN";
        return (
          <button
            key={s.session_id}
            onClick={() => onSelect(s)}
            className={`w-full flex items-center gap-3 px-4 py-3 text-left transition-colors ${
              active ? "bg-wa-bg" : "hover:bg-gray-50"
            } ${needsHuman ? "border-l-4 border-red-500" : "border-l-4 border-transparent"}`}
          >
            <div className="w-10 h-10 rounded-full bg-wa-teal text-white flex items-center justify-center font-semibold text-sm shrink-0">
              {s.customer_phone.slice(-2)}
            </div>
            <div className="flex-1 min-w-0">
              <div className="font-medium text-gray-800 text-sm truncate">{s.customer_phone}</div>
              <div className="flex items-center gap-2 mt-0.5">
                <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium ${STATUS_STYLES[s.status]}`}>
                  {STATUS_LABEL[s.status] || s.status}
                </span>
                <span className="text-[10px] text-gray-400">{s.message_count || 0} msgs</span>
              </div>
            </div>
            <span className="text-[10px] text-gray-400 shrink-0">{timeAgo(s.last_message_at)}</span>
          </button>
        );
      })}
    </div>
  );
}
