import { themeFor } from "../tenants";

export default function WorkspaceRail({ tenants, activeTenant, onSelect, onBroadcast, view, onViewChange, onLogout }) {
  return (
    <nav className="w-[68px] shrink-0 bg-rail flex flex-col items-center py-4 gap-2">
      {/* Brand mark */}
      <div className="w-10 h-10 rounded-xl bg-brand flex items-center justify-center mb-2 shadow-lift">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
          <path d="M12 2a10 10 0 00-8.7 14.9L2 22l5.3-1.4A10 10 0 1012 2z" stroke="#fff" strokeWidth="1.6" fill="none"/>
          <circle cx="9" cy="12" r="1.3" fill="#fff"/>
          <circle cx="12" cy="12" r="1.3" fill="#fff"/>
          <circle cx="15" cy="12" r="1.3" fill="#fff"/>
        </svg>
      </div>

      <div className="w-7 h-px bg-white/10 mb-1" />

      {/* Tenant workspaces */}
      {tenants.map((t) => {
        const th = themeFor(t.tenant_id);
        const active = activeTenant === t.tenant_id;
        return (
          <button
            key={t.tenant_id}
            onClick={() => onSelect(t.tenant_id)}
            title={t.name}
            className="group relative flex items-center justify-center"
          >
            {/* active indicator bar */}
            <span
              className={`absolute -left-4 w-1 rounded-r-full transition-all ${active ? "h-7" : "h-0 group-hover:h-3"}`}
              style={{ backgroundColor: th.accent }}
            />
            <span
              className={`w-11 h-11 rounded-xl font-display font-semibold text-[17px] flex items-center justify-center transition-all ${
                active ? "text-white shadow-lift scale-105" : "text-white/70 hover:text-white"
              }`}
              style={{
                backgroundColor: active ? th.accent : "rgba(255,255,255,0.08)",
              }}
            >
              {th.initial}
            </span>
          </button>
        );
      })}

      <div className="flex-1" />

      {/* Console view */}
      <RailButton active={view === "console"} onClick={() => onViewChange("console")} title="Live console">
        <path d="M3 3h18v12H3zM8 21h8M12 15v6" strokeLinecap="round" strokeLinejoin="round" />
      </RailButton>

      {/* Admin / manage view */}
      <RailButton active={view === "admin"} onClick={() => onViewChange("admin")} title="Manage data">
        <path d="M12 15a3 3 0 100-6 3 3 0 000 6z" />
        <path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 11-2.83 2.83l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 11-4 0v-.09A1.65 1.65 0 008 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 11-2.83-2.83l.06-.06a1.65 1.65 0 00.33-1.82 1.65 1.65 0 00-1.51-1H2a2 2 0 110-4h.09A1.65 1.65 0 003.6 8a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 112.83-2.83l.06.06a1.65 1.65 0 001.82.33H8a1.65 1.65 0 001-1.51V2a2 2 0 114 0v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 112.83 2.83l-.06.06a1.65 1.65 0 00-.33 1.82V8a1.65 1.65 0 001.51 1H22a2 2 0 110 4h-.09a1.65 1.65 0 00-1.51 1z" strokeLinecap="round" strokeLinejoin="round" />
      </RailButton>

      {/* Broadcast */}
      <RailButton onClick={onBroadcast} title="Broadcast campaign">
        <path d="M3 11l18-5v12L3 14v-3z" strokeLinecap="round" strokeLinejoin="round" />
        <path d="M11.6 16.8a3 3 0 01-5.8-1" strokeLinecap="round" strokeLinejoin="round" />
      </RailButton>

      {/* Logout */}
      <RailButton onClick={onLogout} title="Sign out">
        <path d="M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4M16 17l5-5-5-5M21 12H9" strokeLinecap="round" strokeLinejoin="round" />
      </RailButton>
    </nav>
  );
}

function RailButton({ children, active, onClick, title }) {
  return (
    <button
      onClick={onClick}
      title={title}
      className={`w-11 h-11 rounded-xl flex items-center justify-center transition-colors ${
        active ? "bg-white/15 text-white" : "bg-white/8 text-white/60 hover:text-white hover:bg-white/12"
      }`}
    >
      <svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7">
        {children}
      </svg>
    </button>
  );
}
