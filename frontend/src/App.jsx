import { useEffect, useState, useCallback } from "react";
import { api, isLoggedIn, logout } from "./api/client";
import { themeFor } from "./tenants";
import WorkspaceRail from "./components/WorkspaceRail";
import TenantSwitcher from "./components/TenantSwitcher";
import ConversationList from "./components/ConversationList";
import ChatThread from "./components/ChatThread";
import BroadcastDrawer from "./components/BroadcastDrawer";
import StatStrip from "./components/StatStrip";
import AdminPanel from "./components/AdminPanel";
import Login from "./components/Login";

export default function App() {
  const [authed, setAuthed] = useState(isLoggedIn());
  if (!authed) return <Login onSuccess={() => setAuthed(true)} />;
  return <Console onLogout={() => { logout(); setAuthed(false); }} />;
}

function Console({ onLogout }) {
  const [tenants, setTenants] = useState([]);
  const [activeTenant, setActiveTenant] = useState(null);
  const [sessions, setSessions] = useState([]);
  const [activeSession, setActiveSession] = useState(null);
  const [messages, setMessages] = useState([]);
  const [stats, setStats] = useState(null);
  const [broadcastOpen, setBroadcastOpen] = useState(false);
  const [view, setView] = useState("console"); // "console" | "admin"

  const theme = themeFor(activeTenant);

  // Re-theme the console to the active tenant
  useEffect(() => {
    document.documentElement.style.setProperty("--tenant", theme.accent);
  }, [theme.accent]);

  const loadTenants = useCallback(() => {
    return api.getTenants().then((d) => {
      setTenants(d.tenants);
      setActiveTenant((cur) => cur || (d.tenants[0]?.tenant_id ?? null));
    }).catch(console.error);
  }, []);

  useEffect(() => { loadTenants(); }, [loadTenants]);

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

  const loadMessages = useCallback(() => {
    if (!activeSession || document.hidden) return;
    api.getMessages(activeSession.session_id).then((d) => setMessages(d.messages)).catch(console.error);
  }, [activeSession]);

  useEffect(() => {
    loadMessages();
    const id = setInterval(loadMessages, 3000);
    return () => clearInterval(id);
  }, [loadMessages]);

  useEffect(() => {
    setActiveSession(null);
    setMessages([]);
  }, [activeTenant]);

  // keep active session status fresh
  useEffect(() => {
    if (!activeSession) return;
    const fresh = sessions.find((s) => s.session_id === activeSession.session_id);
    if (fresh && fresh.status !== activeSession.status) setActiveSession(fresh);
  }, [sessions, activeSession]);

  const activeTenantObj = tenants.find((t) => t.tenant_id === activeTenant);

  return (
    <div className="h-full flex bg-canvas text-ink">
      {/* Far-left workspace rail */}
      <WorkspaceRail
        tenants={tenants}
        activeTenant={activeTenant}
        onSelect={setActiveTenant}
        onBroadcast={() => setBroadcastOpen(true)}
        view={view}
        onViewChange={setView}
        onLogout={onLogout}
      />

      {view === "admin" ? (
        <AdminPanel
          tenantId={activeTenant}
          tenantName={activeTenantObj?.name || "—"}
          tenants={tenants}
          onSelectTenant={setActiveTenant}
          onTenantsChanged={loadTenants}
        />
      ) : (
        <>
          {/* Middle: switcher + stats + conversation list */}
          <section className="w-[370px] shrink-0 flex flex-col border-r border-hair bg-surface">
            <header className="px-4 pt-4 pb-3 border-b border-hair">
              <TenantSwitcher tenants={tenants} activeTenant={activeTenant} onSelect={setActiveTenant} />
              <div className="flex items-center gap-1.5 text-[11px] font-medium text-faint mt-3 px-1">
                <span className="w-1.5 h-1.5 rounded-full accent-bg animate-pulsedot" />
                <span className="uppercase tracking-[0.12em]">Live</span>
                <span className="text-muted normal-case tracking-normal">· {theme.persona}</span>
              </div>
              <StatStrip stats={stats} />
            </header>

            <div className="flex-1 overflow-y-auto">
              <ConversationList
                sessions={sessions}
                activeId={activeSession?.session_id}
                onSelect={setActiveSession}
              />
            </div>
          </section>

          {/* Right: chat thread */}
          <main className="flex-1 min-w-0 flex flex-col">
            <ChatThread session={activeSession} messages={messages} />
          </main>
        </>
      )}

      <BroadcastDrawer
        open={broadcastOpen}
        onClose={() => setBroadcastOpen(false)}
        tenantId={activeTenant}
        tenants={tenants}
        sessions={sessions}
      />
    </div>
  );
}
