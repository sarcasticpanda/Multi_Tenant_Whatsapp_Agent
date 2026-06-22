import { useState, useRef, useEffect } from "react";
import { themeFor } from "../tenants";

/** Searchable tenant switcher — scales to hundreds of tenants (vs. a tile per tenant). */
export default function TenantSwitcher({ tenants, activeTenant, onSelect }) {
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const ref = useRef(null);

  useEffect(() => {
    const close = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, []);

  const active = tenants.find((t) => t.tenant_id === activeTenant);
  const th = themeFor(activeTenant);
  const filtered = tenants.filter(
    (t) => t.name.toLowerCase().includes(q.toLowerCase()) || t.tenant_id.toLowerCase().includes(q.toLowerCase())
  );

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center gap-2.5 px-2.5 py-2 rounded-xl border border-hair bg-surface hover:bg-canvas transition-colors"
      >
        <span className="w-8 h-8 rounded-lg flex items-center justify-center text-white font-display font-semibold text-[14px] shrink-0"
          style={{ backgroundColor: th.accent }}>{th.initial}</span>
        <span className="flex-1 min-w-0 text-left">
          <span className="block font-display font-semibold text-[14px] leading-tight truncate">{active?.name || "Select tenant"}</span>
          <span className="block text-[11px] text-faint">{tenants.length} tenant{tenants.length === 1 ? "" : "s"}</span>
        </span>
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#A99F92" strokeWidth="2" className={`transition-transform ${open ? "rotate-180" : ""}`}>
          <path d="M6 9l6 6 6-6" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </button>

      {open && (
        <div className="absolute z-30 mt-1.5 w-full bg-surface border border-hair rounded-xl shadow-lift overflow-hidden">
          <div className="p-2 border-b border-hair">
            <input
              autoFocus value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search tenants…"
              className="w-full text-[13px] px-2.5 py-1.5 rounded-lg bg-canvas border border-hair focus:outline-none focus:border-brand"
            />
          </div>
          <ul className="max-h-72 overflow-y-auto py-1">
            {filtered.map((t) => {
              const tt = themeFor(t.tenant_id);
              const isActive = t.tenant_id === activeTenant;
              return (
                <li key={t.tenant_id}>
                  <button
                    onClick={() => { onSelect(t.tenant_id); setOpen(false); setQ(""); }}
                    className={`w-full flex items-center gap-2.5 px-3 py-2 text-left hover:bg-canvas transition-colors ${isActive ? "bg-canvas" : ""}`}
                  >
                    <span className="w-7 h-7 rounded-lg flex items-center justify-center text-white font-display font-semibold text-[12px] shrink-0"
                      style={{ backgroundColor: tt.accent }}>{tt.initial}</span>
                    <span className="flex-1 min-w-0">
                      <span className="block text-[13px] font-medium truncate">{t.name}</span>
                      <span className="block font-mono text-[10px] text-faint">{t.tenant_id}</span>
                    </span>
                    {isActive && <span className="w-1.5 h-1.5 rounded-full accent-bg" />}
                  </button>
                </li>
              );
            })}
            {filtered.length === 0 && <li className="px-3 py-3 text-[12px] text-faint text-center">No tenants match</li>}
          </ul>
        </div>
      )}
    </div>
  );
}
