export default function WorkspaceRail({ onBroadcast, view, onViewChange, onLogout, listOpen, onToggleList }) {
  return (
    <nav className="w-[64px] shrink-0 bg-rail flex flex-col items-center py-4 gap-2">
      {/* Brand mark — concentric "orchestrator" node. Click = back to live console (home). */}
      <button
        onClick={() => onViewChange("console")}
        title="Home — live console"
        className="w-10 h-10 rounded-xl bg-gradient-to-br from-brand to-brand-deep flex items-center justify-center mb-2 shadow-lift transition-transform hover:scale-105 active:scale-95"
      >
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none">
          <circle cx="12" cy="12" r="9" stroke="#fff" strokeWidth="1.5" opacity="0.35" />
          <circle cx="12" cy="12" r="4.5" fill="#fff" />
          <circle cx="20" cy="6" r="2" fill="#fff" />
          <circle cx="5" cy="18" r="2" fill="#fff" />
          <path d="M12 12l7-5M12 12l-6 5" stroke="#fff" strokeWidth="1.3" opacity="0.6" />
        </svg>
      </button>

      {/* Collapse / expand the conversation panel */}
      {view === "console" && (
        <RailButton onClick={onToggleList} title={listOpen ? "Hide list" : "Show list"}>
          <path d="M3 6h18M3 12h18M3 18h18" strokeLinecap="round" strokeLinejoin="round" />
        </RailButton>
      )}

      <div className="w-7 h-px bg-white/10 my-1" />

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
