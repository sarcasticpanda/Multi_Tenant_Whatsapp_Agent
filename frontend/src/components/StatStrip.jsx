export default function StatStrip({ stats }) {
  const items = [
    { key: "total_sessions", label: "Total", tone: "text-ink" },
    { key: "active", label: "Active", tone: "accent-text" },
    { key: "resolved", label: "Resolved", tone: "text-ink" },
    { key: "needs_human", label: "Escalated", tone: "text-alert" },
  ];
  return (
    <div className="grid grid-cols-4 gap-2 mt-4">
      {items.map((it) => (
        <div key={it.key} className="rounded-lg bg-canvas border border-hair px-2.5 py-2">
          <div className={`font-mono font-semibold text-[19px] leading-none tabular ${it.tone}`}>
            {stats?.[it.key] ?? "—"}
          </div>
          <div className="text-[10px] text-faint mt-1 uppercase tracking-wider">{it.label}</div>
        </div>
      ))}
    </div>
  );
}
