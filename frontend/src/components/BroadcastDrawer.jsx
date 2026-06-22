import { useState } from "react";
import { api } from "../api/client";

const TEMPLATES = [
  { label: "New Catalog Promo", text: "🎉 Our new collection just dropped! Reply *catalog* to see the latest pieces." },
  { label: "Weekend Sale", text: "This weekend only: up to _30% off_ select items. Reply here to know more!" },
  { label: "Service Reminder", text: "🔧 Time for your car's check-up! Reply to book a service slot this week." },
  { label: "Festive Greeting", text: "Wishing you joy this festive season! 🎊 Reply *offers* for exclusive deals." },
];

export default function BroadcastDrawer({ open, onClose, tenantId, sessions }) {
  const [selected, setSelected] = useState([]);
  const [template, setTemplate] = useState(TEMPLATES[0].text);
  const [sending, setSending] = useState(false);
  const [result, setResult] = useState(null);

  const togglePhone = (phone) => {
    setSelected((prev) =>
      prev.includes(phone) ? prev.filter((p) => p !== phone) : [...prev, phone]
    );
  };

  const selectAll = () => setSelected(sessions.map((s) => s.customer_phone));
  const clearAll = () => setSelected([]);

  const send = async () => {
    if (!selected.length) return;
    setSending(true);
    setResult(null);
    try {
      const r = await api.broadcast({
        tenant_id: tenantId,
        phone_numbers: selected,
        message: template,
      });
      setResult({ ok: true, sent: r.sent?.length || 0, failed: r.failed?.length || 0 });
    } catch (e) {
      setResult({ ok: false, error: e.message });
    } finally {
      setSending(false);
    }
  };

  return (
    <div
      className={`fixed inset-0 z-50 ${open ? "" : "pointer-events-none"}`}
    >
      {/* Backdrop */}
      <div
        className={`absolute inset-0 bg-black/30 transition-opacity ${open ? "opacity-100" : "opacity-0"}`}
        onClick={onClose}
      />
      {/* Drawer */}
      <div
        className={`absolute right-0 top-0 h-full w-full max-w-md bg-white shadow-2xl transition-transform ${
          open ? "translate-x-0" : "translate-x-full"
        } flex flex-col`}
      >
        <div className="bg-wa-dark text-white px-5 py-4 flex items-center justify-between">
          <div>
            <h2 className="font-semibold">📢 Broadcast Campaign</h2>
            <p className="text-xs text-white/70">Send a template to selected customers</p>
          </div>
          <button onClick={onClose} className="text-white/80 hover:text-white text-xl">✕</button>
        </div>

        <div className="flex-1 overflow-y-auto p-5 space-y-5">
          {/* Template picker */}
          <div>
            <label className="text-xs font-semibold text-gray-500 uppercase">Template Message</label>
            <div className="grid grid-cols-2 gap-2 mt-2">
              {TEMPLATES.map((t) => (
                <button
                  key={t.label}
                  onClick={() => setTemplate(t.text)}
                  className={`text-xs px-2 py-2 rounded-lg border text-left ${
                    template === t.text
                      ? "border-wa-green bg-green-50 text-gray-800"
                      : "border-gray-200 text-gray-600 hover:border-gray-300"
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
              className="w-full mt-2 text-sm border border-gray-200 rounded-lg p-2 focus:outline-none focus:border-wa-green"
            />
          </div>

          {/* Recipient cohort */}
          <div>
            <div className="flex items-center justify-between">
              <label className="text-xs font-semibold text-gray-500 uppercase">
                Recipients ({selected.length})
              </label>
              <div className="flex gap-2">
                <button onClick={selectAll} className="text-[11px] text-wa-teal hover:underline">Select all</button>
                <button onClick={clearAll} className="text-[11px] text-gray-400 hover:underline">Clear</button>
              </div>
            </div>
            <div className="mt-2 border border-gray-200 rounded-lg divide-y max-h-60 overflow-y-auto">
              {sessions.length === 0 && (
                <div className="p-3 text-xs text-gray-400 text-center">No customers yet</div>
              )}
              {sessions.map((s) => (
                <label key={s.session_id} className="flex items-center gap-2 px-3 py-2 cursor-pointer hover:bg-gray-50">
                  <input
                    type="checkbox"
                    checked={selected.includes(s.customer_phone)}
                    onChange={() => togglePhone(s.customer_phone)}
                    className="accent-wa-green"
                  />
                  <span className="text-sm text-gray-700">{s.customer_phone}</span>
                </label>
              ))}
            </div>
          </div>

          {result && (
            <div className={`text-sm rounded-lg p-3 ${result.ok ? "bg-green-50 text-green-700" : "bg-red-50 text-red-700"}`}>
              {result.ok
                ? `✓ Sent to ${result.sent} customer(s)${result.failed ? `, ${result.failed} failed` : ""}`
                : `✗ ${result.error}`}
            </div>
          )}
        </div>

        <div className="p-5 border-t">
          <button
            onClick={send}
            disabled={sending || !selected.length}
            className="w-full bg-wa-green text-white font-semibold py-3 rounded-lg disabled:opacity-50 hover:bg-wa-teal transition-colors"
          >
            {sending ? "Sending…" : `Send to ${selected.length} customer(s)`}
          </button>
        </div>
      </div>
    </div>
  );
}
