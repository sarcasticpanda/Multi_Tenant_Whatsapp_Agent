import { useEffect, useRef } from "react";

// Render WhatsApp markdown: *bold*, _italic_
function renderText(text) {
  if (!text) return null;
  const parts = text.split(/(\*[^*]+\*|_[^_]+_)/g);
  return parts.map((p, i) => {
    if (p.startsWith("*") && p.endsWith("*")) return <strong key={i}>{p.slice(1, -1)}</strong>;
    if (p.startsWith("_") && p.endsWith("_")) return <em key={i}>{p.slice(1, -1)}</em>;
    return <span key={i}>{p}</span>;
  });
}

function fmtTime(iso) {
  if (!iso) return "";
  return new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function MediaBlock({ msg }) {
  if (!msg.media_url) return null;
  if (msg.media_type === "IMAGE") {
    return (
      <img
        src={msg.media_url}
        alt="sent media"
        className="rounded-lg mt-1 max-w-[220px] border border-black/5"
        loading="lazy"
      />
    );
  }
  if (msg.media_type === "DOCUMENT") {
    return (
      <a
        href={msg.media_url}
        target="_blank"
        rel="noreferrer"
        className="flex items-center gap-2 mt-1 bg-white/70 rounded-lg px-3 py-2 border border-black/5 hover:bg-white"
      >
        <span className="text-red-500 text-xl">📄</span>
        <div className="min-w-0">
          <div className="text-xs font-medium text-gray-800 truncate">
            {msg.media_filename || "Document.pdf"}
          </div>
          <div className="text-[10px] text-gray-500">PDF • tap to open</div>
        </div>
      </a>
    );
  }
  return null;
}

export default function ChatThread({ session, messages }) {
  const endRef = useRef(null);
  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  if (!session) {
    return (
      <div className="flex-1 flex items-center justify-center text-gray-400 text-sm chat-bg">
        Select a conversation to view the chat
      </div>
    );
  }

  const needsHuman = session.status === "NEEDS_HUMAN";

  return (
    <div className={`flex-1 flex flex-col ${needsHuman ? "ring-4 ring-red-400 ring-inset" : ""}`}>
      {/* Header */}
      <div className="bg-wa-dark text-white px-4 py-3 flex items-center gap-3 shrink-0">
        <div className="w-9 h-9 rounded-full bg-wa-teal flex items-center justify-center text-sm font-semibold">
          {session.customer_phone.slice(-2)}
        </div>
        <div className="flex-1">
          <div className="font-medium text-sm">{session.customer_phone}</div>
          <div className="text-[11px] text-white/70">{session.status}</div>
        </div>
        {needsHuman && (
          <span className="bg-red-500 text-white text-[11px] px-2 py-1 rounded-full font-semibold">
            ⚠ NEEDS HUMAN
          </span>
        )}
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto chat-bg p-4 space-y-2">
        {messages.map((m) => {
          const outbound = m.direction === "OUTBOUND";
          return (
            <div key={m.message_id} className={`flex ${outbound ? "justify-end" : "justify-start"}`}>
              <div
                className={`max-w-[75%] rounded-lg px-3 py-2 shadow-sm ${
                  outbound ? "bg-wa-bubble" : "bg-white"
                }`}
              >
                {m.text_content && (
                  <div className="text-sm text-gray-800 whitespace-pre-wrap break-words">
                    {renderText(m.text_content)}
                  </div>
                )}
                <MediaBlock msg={m} />
                <div className="flex items-center justify-end gap-1 mt-1">
                  {/* Typing metadata indicator (shows the bot acknowledged + was thinking) */}
                  {m.agent_state === "TYPING" && (
                    <span className="text-[9px] text-blue-400 italic mr-auto">🤖 bot read & started typing…</span>
                  )}
                  <span className="text-[10px] text-gray-400">{fmtTime(m.timestamp)}</span>
                  {outbound && <span className="text-[10px] text-blue-400">✓✓</span>}
                </div>
              </div>
            </div>
          );
        })}

        {/* Live typing bubble — shown while the agent is actively responding */}
        {session.status === "AGENT_RESPONDING" && (
          <div className="flex justify-start">
            <div className="bg-white rounded-lg px-3 py-2 shadow-sm">
              <div className="flex items-center gap-1">
                <span className="text-xs text-gray-500 italic">bot is typing</span>
                <span className="flex gap-0.5">
                  <span className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: "0ms" }} />
                  <span className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: "150ms" }} />
                  <span className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: "300ms" }} />
                </span>
              </div>
            </div>
          </div>
        )}
        <div ref={endRef} />
      </div>
    </div>
  );
}
