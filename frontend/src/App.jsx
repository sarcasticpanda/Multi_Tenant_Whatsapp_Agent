import { useEffect, useState, useCallback } from "react";
import { api } from "./api/client";
import TenantSwitcher from "./components/TenantSwitcher";
import ChatMonitor from "./components/ChatMonitor";
import ChatThread from "./components/ChatThread";
import BroadcastDrawer from "./components/BroadcastDrawer";

export default function App() {
  const [tenants, setTenants] = useState([]);
  const [activeTenant, setActiveTenant] = useState(null);
  const [sessions, setSessions] = useState([]);
  const [activeSession, setActiveSession] = useState(null);
  const [messages, setMessages] = useState([]);
  const [stats, setStats] = useState(null);
  const [broadcastOpen, setBroadcastOpen] = useState(false);

  // Load tenants once
  useEffect(() => {
    api.getTenants().then((d) => {
      setTenants(d.tenants);
      if (d.tenants.length) setActiveTenant(d.tenants[0].tenant_id);
    }).catch(console.error);
  }, []);

  // Load sessions for active tenant + poll every 5s (skip when tab hidden)
  const loadSessions = useCallback(() => {
    if (!activeTenant || document.hidden) return;
    api.getSessions(activeTenant).then((d) => setSessions(d.sessions)).catch(console.error);
    api.getStats(activeTenant).then(setStats).catch(() => {});
  }, [activeTenant]);

  useEffect(() => {
    loadSessions();
    const id = setInterval(loadSessions, 5000);
    return () => clearInterval(id);
  }, [loadSessions]);

  // Load messages for active session + poll every 3s (skip when tab hidden)
  const loadMessages = useCallback(() => {
    if (!activeSession || document.hidden) return;
    api.getMessages(activeSession.session_id).then((d) => setMessages(d.messages)).catch(console.error);
  }, [activeSession]);

  useEffect(() => {
    loadMessages();
    const id = setInterval(loadMessages, 3000);
    return () => clearInterval(id);
  }, [loadMessages]);

  // Reset session when switching tenant
  useEffect(() => {
    setActiveSession(null);
    setMessages([]);
  }, [activeTenant]);

  // Keep activeSession status fresh from polled sessions
  useEffect(() => {
    if (activeSession) {
      const fresh = sessions.find((s) => s.session_id === activeSession.session_id);
      if (fresh && fresh.status !== activeSession.status) setActiveSession(fresh);
    }
  }, [sessions]); // eslint-disable-line

  return (
    <div className="h-screen flex flex-col bg-gray-100">
      {/* Top bar */}
      <header className="bg-white border-b px-6 py-3 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-4">
          <h1 className="text-lg font-bold text-gray-800">
            <span className="text-wa-green">●</span> WhatsApp Agent Console
          </h1>
          <TenantSwitcher tenants={tenants} activeTenant={activeTenant} onSelect={setActiveTenant} />
        </div>
        <div className="flex items-center gap-4">
          {stats && (
            <div className="flex gap-3 text-xs">
              <Stat label="Total" value={stats.total_sessions} color="text-gray-700" />
              <Stat label="Active" value={stats.active} color="text-blue-600" />
              <Stat label="Resolved" value={stats.resolved} color="text-green-600" />
              <Stat label="Needs Human" value={stats.needs_human} color="text-red-600" />
            </div>
          )}
          <button
            onClick={() => setBroadcastOpen(true)}
            className="bg-wa-green text-white text-sm font-semibold px-4 py-2 rounded-lg hover:bg-wa-teal transition-colors"
          >
            📢 Broadcast
          </button>
        </div>
      </header>

      {/* Main split */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left: sessions */}
        <aside className="w-80 bg-white border-r flex flex-col shrink-0">
          <div className="px-4 py-2 bg-gray-50 border-b text-xs font-semibold text-gray-500 uppercase">
            Live Conversations
          </div>
          <div className="flex-1 overflow-y-auto">
            <ChatMonitor
              sessions={sessions}
              activeSession={activeSession?.session_id}
              onSelect={setActiveSession}
            />
          </div>
        </aside>

        {/* Right: chat thread */}
        <main className="flex-1 flex flex-col">
          <ChatThread session={activeSession} messages={messages} />
        </main>
      </div>

      <BroadcastDrawer
        open={broadcastOpen}
        onClose={() => setBroadcastOpen(false)}
        tenantId={activeTenant}
        sessions={sessions}
      />
    </div>
  );
}

function Stat({ label, value, color }) {
  return (
    <div className="text-center">
      <div className={`font-bold ${color}`}>{value ?? 0}</div>
      <div className="text-[10px] text-gray-400">{label}</div>
    </div>
  );
}
