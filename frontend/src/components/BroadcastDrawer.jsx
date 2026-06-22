import { useState, useEffect } from "react";
import { api } from "../api/client";

const TEMPLATES = [
  { label: "New Catalog Promo", text: "Our new collection just dropped! Reply *catalog* to browse the latest pieces." },
  { label: "Weekend Sale", text: "This weekend only — up to _30% off_ select items. Reply here to know more." },
  { label: "Service Reminder", text: "Time for your car's check-up. Reply to book a service slot this week." },
  { label: "Festive Greeting", text: "Wishing you joy this festive season. Reply *offers* for exclusive deals." },
];

function fmtPhone(p) {
  const s = String(p || "");
  return s.length >= 12 ? `+${s.slice(0, 2)} ${s.slice(2, 7)} ${s.slice(7)}` : s;
}

export default function BroadcastDrawer({ open, onClose, tenantId, tenants = [], sessions }) {
  const [selected, setSelected] = useState([]);
  const [template, setTemplate] = useState(TEMPLATES[0].text);
  const [sending, setSending] = useState(false);
  const [result, setResult] = useState(null);
  const [targetTenant, setTargetTenant] = useState(tenantId);
  const [targetSessions, setTargetSessions] = useState(sessions);

  useEffect(() => {
    if (open) { setResult(null); setTargetTenant(tenantId); }
  }, [open, tenantId]);

  // Load recipients for whichever tenant is targeted (may differ from the console's active tenant)
  useEffect(() => {
    if (!open || !targetTenant) return;
    if (targetTenant === tenantId) { setTargetSessions(sessions); return; }
    api.getSessions(targetTenant).then((d) => setTargetSessions(d.sessions)).catch(() => setTargetSessions([]));
    setSelected([]);
  }, [open, targetTenant, tenantId, sessions]);

  const phones = [...new Set((targetSessions || []).map((s) => s.customer_phone))];
  const toggle = (p) => setSelected((x) => (x.includes(p) ? x.filter((y) => y !== p) : [...x, p]));

  const send = async () => {
    if (!selected.length) return;
    setSending(true); setResult(null);
    try {
      const r = await api.broadcast({ tenant_id: targetTenant, phone_numbers: selected, message: template });
      setResult({ ok: true, sent: r.sent?.length || 0, failed: r.failed?.length || 0 });
    } catch (e) {
      setResult({ ok: false, error: e.message });
    } finally { setSending(false); }
  };

  return (
    <div className={`fixed inset-0 z-50 ${open ? "" : "pointer-events-none"}`}>
      <div
        className={`absolute inset-0 bg-ink/40 backdrop-blur-[1px] transition-opacity ${open ? "opacity-100" : "opacity-0"}`}
        onClick={onClose}
      />
      <div
        className={`absolute right-0 top-0 h-full w-full max-w-[420px] bg-surface shadow-lift flex flex-col transition-transform duration-[400ms] ease-[cubic-bezier(0.32,0.72,0,1)] ${
          open ? "translate-x-0" : "translate-x-full"
        }`}
      >
        <div className="px-5 py-4 border-b border-hair flex items-start justify-between">
          <div>
            <div className="flex items-center gap-1.5 text-[11px] font-semibold text-faint uppercase tracking-[0.12em]">
              <span className="w-1.5 h-1.5 rounded-full accent-bg" /> Campaign
            </div>
            <h2 className="font-display text-[19px] font-semibold mt-1">Broadcast a message</h2>
          </div>
          <button onClick={onClose} className="w-8 h-8 rounded-lg hover:bg-canvas flex items-center justify-center text-muted">✕</button>
        </div>

        <div className="flex-1 overflow-y-auto p-5 space-y-5">
          <div>
            <label className="text-[11px] font-semibold text-faint uppercase tracking-wider">Tenant</label>
            <select
              value={targetTenant || ""}
              onChange={(e) => setTargetTenant(e.target.value)}
              className="w-full mt-1.5 text-[13px] border border-hair rounded-lg px-2.5 py-2 bg-surface focus:outline-none focus:border-brand"
            >
              {tenants.map((t) => (
                <option key={t.tenant_id} value={t.tenant_id}>{t.name}</option>
              ))}
            </select>
            <p className="text-[11px] text-faint mt-1">Broadcast goes to this brand's customers.</p>
          </div>

          <div>
            <label className="text-[11px] font-semibold text-faint uppercase tracking-wider">Template</label>
            <div className="grid grid-cols-2 gap-2 mt-2">
              {TEMPLATES.map((t) => (
                <button
                  key={t.label}
                  onClick={() => setTemplate(t.text)}
                  className={`text-[12px] px-2.5 py-2 rounded-lg border text-left transition-colors ${
                    template === t.text ? "accent-ring border-transparent bg-canvas" : "border-hair text-muted hover:border-faint"
                  }`}
                >
                  {t.label}
                </button>
              ))}
            </div>
            <textarea
              value={template}
              onChange={(e) => setTemplate(e.target.value)}
              rows={3}
              className="w-full mt-2 text-[13px] border border-hair rounded-lg p-2.5 focus:outline-none focus:border-brand resize-none"
            />
          </div>

          <div>
            <div className="flex items-center justify-between">
              <label className="text-[11px] font-semibold text-faint uppercase tracking-wider">
                Recipients · {selected.length}
              </label>
              <div className="flex gap-3 text-[11px]">
                <button onClick={() => setSelected(phones)} className="accent-text font-medium">All</button>
                <button onClick={() => setSelected([])} className="text-faint">Clear</button>
              </div>
            </div>
            <div className="mt-2 border border-hair rounded-lg divide-y divide-hair max-h-56 overflow-y-auto">
              {phones.length === 0 && <div className="p-3 text-[12px] text-faint text-center">No customers yet</div>}
              {phones.map((p) => (
                <label key={p} className="flex items-center gap-2.5 px-3 py-2.5 cursor-pointer hover:bg-canvas">
                  <input type="checkbox" checked={selected.includes(p)} onChange={() => toggle(p)}
                    className="w-4 h-4 rounded accent-brand" />
                  <span className="font-mono text-[13px] text-ink">{fmtPhone(p)}</span>
                </label>
              ))}
            </div>
          </div>

          {result && (
            <div className={`text-[13px] rounded-lg p-3 ${result.ok ? "bg-brand-soft text-brand-deep" : "bg-alert-soft text-alert"}`}>
              {result.ok
                ? `Sent to ${result.sent} customer${result.sent === 1 ? "" : "s"}${result.failed ? ` · ${result.failed} failed` : ""}`
                : result.error}
            </div>
          )}
        </div>

        <div className="p-5 border-t border-hair">
          <button
            onClick={send}
            disabled={sending || !selected.length}
            className="w-full accent-bg text-white font-medium text-[14px] py-3 rounded-lg disabled:opacity-40 transition-opacity"
          >
            {sending ? "Sending…" : selected.length ? `Send to ${selected.length}` : "Select recipients"}
          </button>
        </div>
      </div>
    </div>
  );
}
