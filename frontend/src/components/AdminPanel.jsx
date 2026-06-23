import { useEffect, useState, useCallback } from "react";
import { api, displayUrl } from "../api/client";
import { themeFor } from "../tenants";

/**
 * Two clean levels:
 *  1. Directory  — list / add / delete tenants (the "which brand" level)
 *  2. Workspace  — drill into ONE tenant to manage its catalog/media/knowledge/settings
 */
export default function AdminPanel({ tenants, onSelectTenant, onTenantsChanged }) {
  const [managing, setManaging] = useState(null);

  const openTenant = (id) => {
    setManaging(id);
    onSelectTenant?.(id);
  };

  if (managing) {
    const tenant = tenants.find((t) => t.tenant_id === managing);
    if (!tenant) { setManaging(null); return null; }
    return <TenantWorkspace tenant={tenant} onBack={() => setManaging(null)} />;
  }
  return <Directory tenants={tenants} onManage={openTenant} onChanged={onTenantsChanged} />;
}

/* =============================== DIRECTORY =============================== */
function Directory({ tenants, onManage, onChanged }) {
  const [adding, setAdding] = useState(false);

  return (
    <div className="flex-1 flex flex-col min-h-0 bg-canvas">
      <header className="px-7 py-6 bg-surface border-b border-hair flex items-end justify-between">
        <div>
          <div className="flex items-center gap-1.5 text-[11px] font-medium text-faint uppercase tracking-[0.14em]">
            <span className="w-1.5 h-1.5 rounded-full accent-bg" /> Manage
          </div>
          <h1 className="font-display text-[22px] font-semibold mt-1.5">Tenants</h1>
          <p className="text-[13px] text-muted mt-0.5">Each tenant is an independent brand with its own bot, catalog and knowledge.</p>
        </div>
        <button onClick={() => setAdding((v) => !v)}
          className="accent-bg text-white text-[13px] font-medium px-4 py-2 rounded-lg">
          {adding ? "Close" : "+ Add tenant"}
        </button>
      </header>

      <div className="flex-1 overflow-y-auto p-7">
        {adding && <AddTenant onChanged={onChanged} onDone={(id) => { setAdding(false); onManage(id); }} />}

        <div className="grid grid-cols-3 gap-4">
          {tenants.map((t) => {
            const th = themeFor(t.tenant_id);
            return (
              <div key={t.tenant_id} className="bg-surface border border-hair rounded-xl p-5 flex flex-col">
                <div className="flex items-center gap-3">
                  <span className="w-10 h-10 rounded-xl flex items-center justify-center font-display font-semibold text-white text-[16px]"
                    style={{ backgroundColor: th.accent }}>{th.initial}</span>
                  <div className="min-w-0">
                    <div className="font-display font-semibold text-[15px] truncate">{t.name}</div>
                    <div className="font-mono text-[11px] text-faint">{t.tenant_id}</div>
                  </div>
                </div>
                <span className={`inline-flex items-center gap-1 text-[10.5px] mt-4 px-2 py-0.5 rounded-full w-fit ${t.is_active ? "bg-brand-soft text-brand-deep" : "bg-canvas text-faint"}`}>
                  <span className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: t.is_active ? "#12A88E" : "#9AA4B0" }} />
                  {t.is_active ? "active" : "inactive"}
                </span>
                <div className="flex items-center gap-2 mt-5 pt-4 border-t border-hair">
                  <button onClick={() => onManage(t.tenant_id)}
                    className="text-[13px] font-medium accent-text">Manage →</button>
                  <button
                    onClick={async () => {
                      if (window.confirm(`Delete "${t.name}" and ALL its data? This cannot be undone.`)) {
                        await api.deleteTenant(t.tenant_id); await onChanged?.();
                      }
                    }}
                    className="text-[13px] text-faint hover:text-alert ml-auto">Delete</button>
                </div>
              </div>
            );
          })}
        </div>

        <RoutingPanel tenants={tenants} />
      </div>
    </div>
  );
}

/* ---------------------------- Customer routing ---------------------------- */
function RoutingPanel({ tenants }) {
  const [open, setOpen] = useState(false);
  const [routes, setRoutes] = useState([]);
  const [phone, setPhone] = useState("");
  const [tenantId, setTenantId] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState(null);

  const load = useCallback(() => { api.routing().then((d) => setRoutes(d.routes)).catch(console.error); }, []);
  useEffect(() => { if (open) load(); }, [open, load]);
  useEffect(() => { if (!tenantId && tenants[0]) setTenantId(tenants[0].tenant_id); }, [tenants, tenantId]);

  const assign = async () => {
    if (!phone || !tenantId) { setMsg({ err: "Enter a customer number and pick a tenant" }); return; }
    setBusy(true); setMsg(null);
    try { await api.setRoute(phone, tenantId); setPhone(""); setMsg({ ok: "Assigned" }); load(); }
    catch (e) { setMsg({ err: e.message }); } finally { setBusy(false); }
  };

  return (
    <div className="mt-9 max-w-3xl border-t border-hair pt-6">
      <button onClick={() => setOpen((v) => !v)} className="flex items-center gap-2 text-[13px] font-medium text-muted hover:text-ink">
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2"
          className={`transition-transform ${open ? "rotate-90" : ""}`}><path d="M9 18l6-6-6-6" strokeLinecap="round" strokeLinejoin="round"/></svg>
        Advanced · manual routing override
      </button>
      {!open && (
        <p className="text-[12px] text-faint mt-1.5">
          Routing is automatic — by the customer's words on a shared number, or by each tenant's own WhatsApp number.
          This is an optional manual override for pinning a specific customer to a tenant.
        </p>
      )}
      {!open ? null : (
      <div className="mt-4">
      <p className="text-[13px] text-muted mb-4">
        Optional override. Normally a customer is routed automatically (by their message keywords on a shared
        number, or by the tenant's own number). Use this only to pin a specific customer to a tenant by hand.
      </p>

      <div className="bg-surface border border-hair rounded-xl divide-y divide-hair mb-4">
        {routes.map((r) => {
          const th = themeFor(r.tenant_id);
          return (
            <div key={r.customer_phone} className="flex items-center gap-3 px-4 py-2.5">
              <span className="font-mono text-[13px] text-ink">{r.customer_phone}</span>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#9AA4B0" strokeWidth="2"><path d="M5 12h14M13 6l6 6-6 6" strokeLinecap="round" strokeLinejoin="round"/></svg>
              <span className="inline-flex items-center gap-1.5 text-[12px]">
                <span className="w-2 h-2 rounded-full" style={{ backgroundColor: th.accent }} />{r.tenant_name}
              </span>
              <button onClick={async () => { await api.deleteRoute(r.customer_phone); load(); }}
                className="ml-auto text-faint hover:text-alert text-[12px]">Unassign</button>
            </div>
          );
        })}
        {routes.length === 0 && <div className="px-4 py-3 text-[13px] text-faint">No explicit assignments yet — new customers stick to the first tenant or the number's owner.</div>}
      </div>

      <div className="bg-surface border border-hair rounded-xl p-4 flex items-end gap-3">
        <div className="flex-1"><Field label="Customer number" value={phone} onChange={setPhone} placeholder="919876543210" /></div>
        <div className="flex-1">
          <label className="text-[11px] font-semibold text-faint uppercase tracking-wider">Tenant</label>
          <select value={tenantId} onChange={(e) => setTenantId(e.target.value)}
            className="w-full mt-1 text-[13px] border border-hair rounded-lg px-3 py-2 bg-white focus:outline-none focus:border-brand">
            {tenants.map((t) => <option key={t.tenant_id} value={t.tenant_id}>{t.name}</option>)}
          </select>
        </div>
        <button onClick={assign} disabled={busy} className="accent-bg text-white text-[13px] font-medium px-4 py-2 rounded-lg disabled:opacity-40">{busy ? "Saving…" : "Assign"}</button>
      </div>
      {msg && <div className={`text-[12px] mt-2 ${msg.ok ? "accent-text" : "text-alert"}`}>{msg.ok || msg.err}</div>}
      </div>
      )}
    </div>
  );
}

function AddTenant({ onChanged, onDone }) {
  const [form, setForm] = useState({ name: "", tenant_id: "", system_prompt: "" });
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);
  const slug = (s) => "tenant_" + s.toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "").slice(0, 24);

  const create = async () => {
    if (!form.name || !form.system_prompt) { setErr("Brand name and bot instructions are required"); return; }
    setBusy(true); setErr(null);
    try {
      const tenant_id = form.tenant_id || slug(form.name);
      await api.createTenant({ tenant_id, name: form.name, system_prompt: form.system_prompt, media_library: {} });
      await onChanged?.();
      onDone(tenant_id);
    } catch (e) { setErr(e.message.replace(/^.*detail":"?/, "").replace(/"?}.*$/, "")); setBusy(false); }
  };

  return (
    <div className="bg-surface border border-hair rounded-xl p-5 mb-6 max-w-2xl">
      <div className="font-display font-semibold text-[15px] mb-4">New tenant</div>
      <div className="grid grid-cols-2 gap-3">
        <Field label="Brand name" value={form.name} onChange={(v) => setForm({ ...form, name: v })} placeholder="Bloom Florists" />
        <Field label="Tenant id (optional)" value={form.tenant_id} onChange={(v) => setForm({ ...form, tenant_id: v })} placeholder="auto from name" />
      </div>
      <div className="mt-3">
        <label className="text-[11px] font-semibold text-faint uppercase tracking-wider">Bot instructions (personality & rules)</label>
        <textarea rows={4} value={form.system_prompt} onChange={(e) => setForm({ ...form, system_prompt: e.target.value })}
          placeholder="You are Rose, a friendly florist assistant. Help customers pick bouquets, quote prices from your knowledge base, and send arrangement photos…"
          className="w-full mt-1 text-[13px] border border-hair rounded-lg p-2.5 focus:outline-none focus:border-brand resize-none" />
      </div>
      {err && <div className="text-[12px] text-alert mt-2">{err}</div>}
      <div className="mt-4 bg-canvas rounded-lg px-3 py-2.5 text-[12px] text-muted">
        <span className="font-medium text-ink">Next, you'll add this brand's data:</span> upload catalog PDFs or
        product images with descriptions (Catalog), map keywords to files like <span className="font-mono">catalog → file.pdf</span> (Media),
        and add FAQ text (Knowledge).
      </div>
      <button onClick={create} disabled={busy}
        className="mt-4 accent-bg text-white text-[13px] font-medium px-4 py-2 rounded-lg disabled:opacity-40">
        {busy ? "Creating…" : "Create & set up"}
      </button>
    </div>
  );
}

/* =============================== WORKSPACE =============================== */
const TABS = ["Catalog", "Media", "Knowledge", "Settings"];

function TenantWorkspace({ tenant, onBack }) {
  const [tab, setTab] = useState("Catalog");
  const [counts, setCounts] = useState({});
  const th = themeFor(tenant.tenant_id);

  const refreshCounts = useCallback(() => {
    Promise.all([
      api.catalog(tenant.tenant_id).then((d) => d.items.length).catch(() => 0),
      api.knowledge(tenant.tenant_id).then((d) => d.docs.length).catch(() => 0),
      // media_library isn't in the minimal tenant list — read it from full admin data
      api.adminTenants().then((d) => {
        const full = d.tenants.find((t) => t.tenant_id === tenant.tenant_id);
        return Object.keys(full?.media_library || {}).length;
      }).catch(() => 0),
    ]).then(([Catalog, Knowledge, Media]) =>
      setCounts({ Catalog, Knowledge, Media })
    );
  }, [tenant]);
  useEffect(() => { refreshCounts(); }, [refreshCounts, tab]);
  return (
    <div className="flex-1 flex flex-col min-h-0 bg-canvas">
      <header className="px-7 pt-5 pb-0 bg-surface border-b border-hair">
        <button onClick={onBack} className="flex items-center gap-1.5 text-[12px] text-muted hover:text-ink mb-3">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M15 18l-6-6 6-6" strokeLinecap="round" strokeLinejoin="round"/></svg>
          All tenants
        </button>
        <div className="flex items-center gap-3">
          <span className="w-9 h-9 rounded-lg flex items-center justify-center font-display font-semibold text-white text-[15px]"
            style={{ backgroundColor: th.accent }}>{th.initial}</span>
          <div>
            <h1 className="font-display text-[20px] font-semibold leading-tight">{tenant.name}</h1>
            <div className="font-mono text-[11px] text-faint">{tenant.tenant_id}</div>
          </div>
        </div>
        <nav className="flex gap-1 mt-4">
          {TABS.map((t) => (
            <button key={t} onClick={() => setTab(t)}
              className={`px-3.5 py-2 text-[13px] font-medium rounded-t-lg border-b-2 transition-colors flex items-center gap-1.5 ${
                tab === t ? "accent-text border-current" : "text-muted border-transparent hover:text-ink"}`}>
              {t}
              {counts[t] != null && (
                <span className={`text-[10px] px-1.5 rounded-full ${tab === t ? "bg-brand-soft text-brand-deep" : "bg-canvas text-faint"}`}>{counts[t]}</span>
              )}
            </button>
          ))}
        </nav>
      </header>
      <div className="flex-1 overflow-y-auto p-7">
        {tab === "Catalog" && <CatalogTab tenantId={tenant.tenant_id} onChange={refreshCounts} />}
        {tab === "Media" && <MediaTab tenantId={tenant.tenant_id} onChange={refreshCounts} />}
        {tab === "Knowledge" && <KnowledgeTab tenantId={tenant.tenant_id} onChange={refreshCounts} />}
        {tab === "Settings" && <SettingsTab tenant={tenant} />}
      </div>
    </div>
  );
}

/* ------------------------------- Catalog ------------------------------- */
function CatalogTab({ tenantId }) {
  const [items, setItems] = useState([]);
  const [busy, setBusy] = useState(false);
  const [form, setForm] = useState({ name: "", price: "", description: "", file: null });
  const [msg, setMsg] = useState(null);
  const [ingestTrigger, setIngestTrigger] = useState(0);

  const load = useCallback(() => { api.catalog(tenantId).then((d) => setItems(d.items)).catch(console.error); }, [tenantId]);
  useEffect(() => { load(); }, [load]);

  const add = async () => {
    if (!form.name || !form.file) { setMsg({ err: "Name and image are required" }); return; }
    setBusy(true); setMsg(null);
    try { await api.addCatalog(tenantId, form); setForm({ name: "", price: "", description: "", file: null }); setMsg({ ok: "Added & indexed for search" }); load(); }
    catch (e) { setMsg({ err: e.message }); } finally { setBusy(false); }
  };

  return (
    <TabLayout
      intro="The products your agent can show and describe. Add photos, prices and details — or import a whole catalog PDF at once. Customers find these by describing what they want."
      count={items.length}
      countLabel="product"
      aside={
        <SidebarCard title="Add a product">
          <Field label="Name" value={form.name} onChange={(v) => setForm({ ...form, name: v })} placeholder="Milano Sofa" />
          <Field label="Price" value={form.price} onChange={(v) => setForm({ ...form, price: v })} placeholder="Rs 1,85,000" className="mt-3" />
          <Field label="Description" hint="leave blank to auto-generate from the image"
            value={form.description} onChange={(v) => setForm({ ...form, description: v })} placeholder="Italian leather, walnut frame…" className="mt-3" />
          <div className="mt-3">
            <label className="text-[11px] font-semibold text-faint uppercase tracking-wider">
              Product image <span className="normal-case font-normal text-faint/80 tracking-normal">· JPG/PNG — a PDF goes in Media</span>
            </label>
            <input type="file" accept="image/png,image/jpeg,image/webp" onChange={(e) => setForm({ ...form, file: e.target.files[0] })}
              className="block mt-1.5 w-full text-[12.5px] text-muted file:mr-3 file:px-3 file:py-1.5 file:rounded-lg file:border-0 file:bg-canvas file:text-ink file:text-[12px] file:cursor-pointer" />
          </div>
          {msg && <div className={`text-[12px] mt-3 ${msg.ok ? "accent-text" : "text-alert"}`}>{msg.ok || msg.err}</div>}
          <button onClick={add} disabled={busy} className="mt-4 w-full accent-bg text-white text-[13px] font-medium px-4 py-2.5 rounded-lg disabled:opacity-40">
            {busy ? "Uploading…" : "Add product"}
          </button>
        </SidebarCard>
      }
    >
      <PdfImport tenantId={tenantId} onDone={load} onStarted={() => setIngestTrigger((t) => t + 1)} />
      <IngestProgress tenantId={tenantId} trigger={ingestTrigger} onDone={load} />
      {items.length === 0 ? (
        <EmptyState icon="box" title="No products yet" hint="Import a catalog PDF above, or add your first product on the right." />
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4 mt-5">
          {items.map((it) => (
            <div key={it.item_id} className="bg-surface border border-hair rounded-xl overflow-hidden group hover:shadow-card transition-shadow">
              <div className="relative">
                <img src={displayUrl(it.image_url)} alt="" className="w-full h-36 object-cover bg-canvas" loading="lazy" />
                <button onClick={async () => { await api.deleteCatalog(it.item_id); load(); }}
                  className="absolute top-2 right-2 bg-white/90 backdrop-blur text-faint hover:text-alert text-[11px] font-medium px-2 py-1 rounded-md opacity-0 group-hover:opacity-100 transition-opacity">Remove</button>
              </div>
              <div className="p-3.5">
                <div className="flex items-baseline justify-between gap-2">
                  <div className="font-display font-semibold text-[14px] truncate">{it.name}</div>
                  {it.price && <div className="font-mono text-[12px] accent-text shrink-0">{it.price}</div>}
                </div>
                <p className="text-[11.5px] text-muted mt-1 line-clamp-2 leading-relaxed">{it.ai_description}</p>
              </div>
            </div>
          ))}
        </div>
      )}
    </TabLayout>
  );
}

function PdfImport({ tenantId, onDone, onStarted }) {
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);
  const onPick = async (e) => {
    const file = e.target.files[0]; if (!file) return;
    setBusy(true); setResult(null);
    try {
      await api.ingestPdf(tenantId, file);
      setResult(null);
      onStarted?.();   // hand off to the live progress indicator
    } catch (err) { setResult({ ok: false, error: err.message }); }
    finally { setBusy(false); e.target.value = ""; }
  };
  return (
    <div className="bg-brand-soft/60 border border-brand/20 rounded-xl p-4 mb-5">
      <div className="flex items-center gap-3">
        <span className="w-9 h-9 rounded-lg bg-surface flex items-center justify-center shrink-0">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#0B5C4E" strokeWidth="1.6"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" strokeLinejoin="round"/><path d="M14 2v6h6" strokeLinejoin="round"/></svg>
        </span>
        <div className="flex-1">
          <div className="font-display font-semibold text-[14px] text-brand-deep">Import a catalog PDF</div>
          <div className="text-[12px] text-muted">Extracts product images <b>and</b> the text — the agent can show items <b>and</b> answer about them.</div>
        </div>
        <label className="shrink-0">
          <span className={`inline-block accent-bg text-white text-[13px] font-medium px-4 py-2 rounded-lg cursor-pointer ${busy ? "opacity-50 pointer-events-none" : ""}`}>{busy ? "Processing…" : "Upload PDF"}</span>
          <input type="file" accept="application/pdf" className="hidden" onChange={onPick} disabled={busy} />
        </label>
      </div>
      {result && <div className={`text-[12px] mt-3 ${result.ok ? "text-brand-deep" : "text-alert"}`}>
        {result.ok ? (result.note || "Indexing in the background — products and knowledge appear shortly.") : result.error}
      </div>}
    </div>
  );
}

/* ------------------------------- Media ------------------------------- */
function MediaTab({ tenantId }) {
  const [tenant, setTenant] = useState(null);
  const [keyword, setKeyword] = useState("");
  const [file, setFile] = useState(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState(null);
  const [ingestTrigger, setIngestTrigger] = useState(0);
  const load = useCallback(() => { api.adminTenants().then((d) => setTenant(d.tenants.find((t) => t.tenant_id === tenantId))).catch(console.error); }, [tenantId]);
  useEffect(() => { load(); }, [load]);

  const add = async () => {
    if (!keyword || !file) return;
    setBusy(true); setMsg(null);
    const wasPdf = (file.name || "").toLowerCase().endsWith(".pdf");
    try {
      await api.addMedia(tenantId, keyword, file);
      setKeyword(""); setFile(null); load();
      if (wasPdf) setIngestTrigger((t) => t + 1); else setMsg("Added.");
    } catch (e) { setMsg(e.message); } finally { setBusy(false); }
  };
  const lib = tenant?.media_library || {};

  return (
    <TabLayout
      intro={<>Ready-to-send files, each mapped to a keyword. When a customer asks for one — e.g. <span className="font-mono text-ink">“send the catalog”</span> — the agent attaches the matching file automatically.</>}
      count={Object.keys(lib).length}
      countLabel="file"
      aside={
        <SidebarCard title="Add a file">
          <Field label="Keyword" hint="what a customer might ask for" value={keyword} onChange={setKeyword} placeholder="catalog" />
          <div className="mt-3">
            <label className="text-[11px] font-semibold text-faint uppercase tracking-wider">File (PDF or image)</label>
            <input type="file" onChange={(e) => setFile(e.target.files[0])}
              className="block mt-1.5 w-full text-[12.5px] text-muted file:mr-2 file:px-2.5 file:py-1.5 file:rounded-lg file:border-0 file:bg-canvas file:text-ink file:cursor-pointer" />
          </div>
          <button onClick={add} disabled={busy} className="mt-4 w-full accent-bg text-white text-[13px] font-medium px-4 py-2.5 rounded-lg disabled:opacity-40">{busy ? "Uploading…" : "Add file"}</button>
          {msg && <div className="text-[12px] mt-3 accent-text leading-relaxed">{msg}</div>}
        </SidebarCard>
      }
    >
      <IngestProgress tenantId={tenantId} trigger={ingestTrigger} onDone={load} />
      {Object.keys(lib).length === 0 ? (
        <EmptyState icon="file" title="No files yet" hint="Add a file on the right and give it a keyword the agent can match." />
      ) : (
        <div className="bg-surface border border-hair rounded-xl divide-y divide-hair">
          {Object.entries(lib).map(([k, url]) => {
            const isPdf = String(url).toLowerCase().endsWith(".pdf");
            return (
              <div key={k} className="flex items-center gap-3 px-4 py-3">
                <span className={`w-8 h-8 rounded-lg flex items-center justify-center shrink-0 ${isPdf ? "bg-alert/10" : "bg-brand-soft"}`}>
                  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke={isPdf ? "#C4543F" : "#0B5C4E"} strokeWidth="1.7">
                    {isPdf
                      ? <><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" strokeLinejoin="round"/><path d="M14 2v6h6" strokeLinejoin="round"/></>
                      : <><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><path d="M21 15l-5-5L5 21" strokeLinejoin="round"/></>}
                  </svg>
                </span>
                <span className="font-mono text-[12px] bg-canvas px-2 py-0.5 rounded text-ink shrink-0">{k}</span>
                <a href={displayUrl(url)} target="_blank" rel="noreferrer" className="text-[12px] text-muted truncate flex-1 hover:accent-text">{url.split("/").pop()}</a>
                <button onClick={async () => { await api.removeMedia(tenantId, k); load(); }} className="text-faint hover:text-alert text-[12px] shrink-0">Remove</button>
              </div>
            );
          })}
        </div>
      )}
    </TabLayout>
  );
}

/* ------------------------------- Knowledge ------------------------------- */
function KnowledgeTab({ tenantId }) {
  const [docs, setDocs] = useState([]);
  const [form, setForm] = useState({ title: "", content: "" });
  const [busy, setBusy] = useState(false);
  const load = useCallback(() => { api.knowledge(tenantId).then((d) => setDocs(d.docs)).catch(console.error); }, [tenantId]);
  useEffect(() => { load(); }, [load]);
  const add = async () => { if (!form.title || !form.content) return; setBusy(true); try { await api.addKnowledge({ tenant_id: tenantId, doc_type: "faq", ...form }); setForm({ title: "", content: "" }); load(); } finally { setBusy(false); } };

  // Manual entries shown individually; PDF-imported chunks grouped by their source file.
  const manual = docs.filter((d) => !d.source_pdf);
  const byPdf = {};
  docs.filter((d) => d.source_pdf).forEach((d) => { (byPdf[d.source_pdf] ||= []).push(d); });
  const pdfGroups = Object.entries(byPdf);

  return (
    <TabLayout
      intro="The facts your agent answers from — pricing, policies, hours, warranty. Type entries, or import a PDF and the agent can answer questions about its contents."
      count={docs.length}
      countLabel="entry"
      countPlural="entries"
      aside={
        <SidebarCard title="Add an entry">
          <Field label="Title" value={form.title} onChange={(v) => setForm({ ...form, title: v })} placeholder="Delivery Policy" />
          <div className="mt-3">
            <label className="text-[11px] font-semibold text-faint uppercase tracking-wider">Content</label>
            <textarea rows={6} value={form.content} onChange={(e) => setForm({ ...form, content: e.target.value })} placeholder="We deliver across India in 4–10 weeks…"
              className="w-full mt-1.5 text-[13px] border border-hair rounded-lg p-2.5 focus:outline-none focus:border-brand resize-none leading-relaxed" />
          </div>
          <button onClick={add} disabled={busy} className="mt-4 w-full accent-bg text-white text-[13px] font-medium px-4 py-2.5 rounded-lg disabled:opacity-40">{busy ? "Saving…" : "Add entry"}</button>
        </SidebarCard>
      }
    >
      <KnowledgePdfImport tenantId={tenantId} onDone={load} />
      {docs.length === 0 ? (
        <EmptyState icon="book" title="No knowledge yet" hint="Type an entry on the right, or import a PDF the agent can answer from." />
      ) : (
        <div className="space-y-3 mt-5">
          {/* Imported documents — grouped, one Remove deletes the whole file */}
          {pdfGroups.map(([src, chunks]) => (
            <div key={src} className="bg-surface border border-hair rounded-xl px-4 py-3.5 flex items-center gap-3">
              <span className="w-8 h-8 rounded-lg bg-alert/10 flex items-center justify-center shrink-0">
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#C4543F" strokeWidth="1.7"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" strokeLinejoin="round"/><path d="M14 2v6h6" strokeLinejoin="round"/></svg>
              </span>
              <div className="min-w-0 flex-1">
                <div className="font-display font-semibold text-[13.5px] truncate">{src}</div>
                <div className="text-[11.5px] text-muted">Imported document · {chunks.length} searchable chunk{chunks.length === 1 ? "" : "s"}</div>
              </div>
              <button onClick={async () => { if (window.confirm(`Remove “${src}” and all ${chunks.length} chunks?`)) { await api.deleteKnowledgeBySource(tenantId, src); load(); } }}
                className="text-faint hover:text-alert text-[12px] shrink-0">Remove</button>
            </div>
          ))}
          {/* Manual entries */}
          {manual.length > 0 && (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
              {manual.map((d) => (
                <div key={d.doc_id} className="bg-surface border border-hair rounded-xl px-4 py-3.5 hover:shadow-card transition-shadow">
                  <div className="flex items-start justify-between gap-2">
                    <span className="font-display font-semibold text-[13.5px]">{d.title}</span>
                    <button onClick={async () => { await api.deleteKnowledge(d.doc_id); load(); }} className="text-faint hover:text-alert text-[12px] shrink-0">Remove</button>
                  </div>
                  <p className="text-[12px] text-muted mt-1.5 line-clamp-3 leading-relaxed">{d.content}</p>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </TabLayout>
  );
}

function KnowledgePdfImport({ tenantId, onDone }) {
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);
  const onPick = async (e) => {
    const file = e.target.files[0]; if (!file) return;
    setBusy(true); setResult(null);
    try { const r = await api.ingestKnowledgePdf(tenantId, file); setResult({ ok: true, ...r }); onDone?.(); }
    catch (err) { setResult({ ok: false, error: err.message }); }
    finally { setBusy(false); e.target.value = ""; }
  };
  return (
    <div className="bg-brand-soft/60 border border-brand/20 rounded-xl p-4">
      <div className="flex items-center gap-3">
        <span className="w-9 h-9 rounded-lg bg-surface flex items-center justify-center shrink-0">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#0B5C4E" strokeWidth="1.6"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" strokeLinejoin="round"/><path d="M14 2v6h6" strokeLinejoin="round"/></svg>
        </span>
        <div className="flex-1">
          <div className="font-display font-semibold text-[14px] text-brand-deep">Import a PDF as knowledge</div>
          <div className="text-[12px] text-muted">Reads the document's text so the agent can answer questions about its contents.</div>
        </div>
        <label className="shrink-0">
          <span className={`inline-block accent-bg text-white text-[13px] font-medium px-4 py-2 rounded-lg cursor-pointer ${busy ? "opacity-50 pointer-events-none" : ""}`}>{busy ? "Reading…" : "Upload PDF"}</span>
          <input type="file" accept="application/pdf" className="hidden" onChange={onPick} disabled={busy} />
        </label>
      </div>
      {result && <div className={`text-[12px] mt-3 ${result.ok ? "text-brand-deep" : "text-alert"}`}>
        {result.ok ? `Indexed ${result.text_chunks} text chunk(s) from ${result.pages} page(s).${result.note ? " " + result.note : ""}` : result.error}
      </div>}
    </div>
  );
}

/* ------------------------------- Settings ------------------------------- */
function SettingsTab({ tenant }) {
  // The list passed in is minimal (id/name only). Load the FULL tenant so the
  // prompt / phone_number_id aren't blank — saving a blank would wipe them.
  const [loaded, setLoaded] = useState(false);
  const [name, setName] = useState("");
  const [prompt, setPrompt] = useState("");
  const [phoneId, setPhoneId] = useState("");
  const [saved, setSaved] = useState(false);
  const [err, setErr] = useState(null);

  useEffect(() => {
    let alive = true;
    api.adminTenants().then((d) => {
      const full = d.tenants.find((t) => t.tenant_id === tenant.tenant_id);
      if (!alive || !full) return;
      setName(full.name || "");
      setPrompt(full.system_prompt || "");
      setPhoneId(full.whatsapp_phone_number_id || "");
      setLoaded(true);
    }).catch(console.error);
    return () => { alive = false; };
  }, [tenant.tenant_id]);

  const save = async () => {
    if (!prompt.trim()) { setErr("System prompt can't be empty — the bot needs it to know how to answer."); return; }
    setErr(null);
    await api.updateTenant(tenant.tenant_id, { name, system_prompt: prompt, whatsapp_phone_number_id: phoneId.trim() });
    setSaved(true); setTimeout(() => setSaved(false), 2000);
  };

  if (!loaded) return <div className="text-[13px] text-faint">Loading settings…</div>;

  return (
    <div className="max-w-3xl">
      <Field label="Brand name" value={name} onChange={setName} />
      <div className="mt-4">
        <label className="text-[11px] font-semibold text-faint uppercase tracking-wider">System prompt (bot personality & rules)</label>
        <textarea rows={12} value={prompt} onChange={(e) => setPrompt(e.target.value)}
          className="w-full mt-1 text-[13px] font-mono leading-relaxed border border-hair rounded-lg p-3 focus:outline-none focus:border-brand resize-none" />
      </div>
      <div className="mt-4">
        <Field label="WhatsApp number ID" hint="this tenant's own number — share the test number to route by keywords"
          value={phoneId} onChange={setPhoneId} placeholder="e.g. 1095181447021644" />
        <p className="text-[11px] text-faint mt-1.5 leading-relaxed">
          Give a tenant its own WhatsApp number ID and messages to that number route here automatically — no manual
          assignment. This is a public identifier (not a secret token), but changing it reroutes the tenant, so edit with care.
        </p>
      </div>
      {err && <div className="text-[12px] text-alert mt-3">{err}</div>}
      <div className="flex items-center gap-3 mt-3">
        <button onClick={save} className="accent-bg text-white text-[13px] font-medium px-4 py-2 rounded-lg">Save changes</button>
        {saved && <span className="text-[12px] accent-text">Saved</span>}
      </div>
      <p className="text-[11px] text-faint mt-3 font-mono">tenant_id: {tenant.tenant_id}</p>
    </div>
  );
}

/* ------------------------------- shared ------------------------------- */
function Field({ label, hint, value, onChange, placeholder, className = "" }) {
  return (
    <div className={className}>
      <label className="text-[11px] font-semibold text-faint uppercase tracking-wider">
        {label}{hint && <span className="normal-case font-normal text-faint/80 tracking-normal"> · {hint}</span>}
      </label>
      <input value={value} onChange={(e) => onChange(e.target.value)} placeholder={placeholder}
        className="w-full mt-1.5 text-[13px] border border-hair rounded-lg px-3 py-2 focus:outline-none focus:border-brand" />
    </div>
  );
}

/* Two-column tab: a full-width intro + scrolling content on the left, a sticky
   action card on the right. Replaces the old left-aligned, half-empty layout. */
function TabLayout({ intro, count, countLabel, countPlural, aside, children }) {
  const plural = countPlural || `${countLabel}s`;
  return (
    <div className="max-w-[1100px]">
      <div className="flex items-baseline justify-between gap-4 mb-5">
        <p className="text-[13px] text-muted leading-relaxed max-w-2xl">{intro}</p>
        {count != null && (
          <span className="shrink-0 text-[12px] text-faint whitespace-nowrap">
            {count} {count === 1 ? countLabel : plural}
          </span>
        )}
      </div>
      <div className="flex gap-7 items-start">
        <div className="flex-1 min-w-0">{children}</div>
        <aside className="w-[330px] shrink-0 sticky top-0">{aside}</aside>
      </div>
    </div>
  );
}

const PHASE_LABEL = {
  starting: "Starting…",
  images: "Extracting product images…",
  text: "Reading & chunking text…",
  indexing: "Building the search index…",
  done: "Done",
};

// Live, animated ingestion progress — polls the server while a PDF is being indexed.
function IngestProgress({ tenantId, trigger, onDone }) {
  const [job, setJob] = useState(null);
  useEffect(() => {
    if (!trigger) return;
    let alive = true, doneSeen = false, extra = 0;
    const started = Date.now();
    setJob({ status: "processing", phase: "starting", items_created: 0, text_chunks: 0, images_found: 0 });
    const finish = () => { clearInterval(id); if (!doneSeen) { doneSeen = true; onDone?.(); } setTimeout(() => { if (alive) setJob(null); }, 5000); };
    const tick = async () => {
      try {
        const { job } = await api.ingestStatus(tenantId);
        if (!alive || !job) return;
        setJob(job);
        if (job.status === "done" || job.status === "error") {
          if (!doneSeen) { doneSeen = true; onDone?.(); }
          extra += 1;
          if (extra >= 2) { clearInterval(id); setTimeout(() => { if (alive) setJob(null); }, 5000); }
        } else if (Date.now() - started > 90000) {
          // Safety net: never spin forever (e.g. a restart killed the job) — finish & refresh.
          setJob((j) => ({ ...(j || {}), status: "done", phase: "done" }));
          finish();
        }
      } catch { /* keep polling */ }
    };
    const id = setInterval(tick, 1500);
    tick();
    return () => { alive = false; clearInterval(id); };
  }, [trigger, tenantId]);

  if (!job) return null;
  const done = job.status === "done";
  const error = job.status === "error";
  const pct = job.images_found > 0 ? Math.min(100, Math.round((job.items_created / job.images_found) * 100)) : null;

  return (
    <div className={`rounded-xl p-4 mb-5 border ${error ? "bg-alert/8 border-alert/25" : "bg-brand-soft/60 border-brand/20"}`}>
      <div className="flex items-center gap-3">
        {error ? (
          <span className="w-8 h-8 rounded-lg bg-alert/15 flex items-center justify-center shrink-0">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#C4543F" strokeWidth="2"><path d="M12 9v4m0 4h.01M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z" strokeLinecap="round" strokeLinejoin="round"/></svg>
          </span>
        ) : done ? (
          <span className="w-8 h-8 rounded-lg bg-brand-soft flex items-center justify-center shrink-0">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#0B5C4E" strokeWidth="2.4"><path d="M20 6 9 17l-5-5" strokeLinecap="round" strokeLinejoin="round"/></svg>
          </span>
        ) : (
          <svg className="w-8 h-8 shrink-0 animate-spin" viewBox="0 0 24 24" fill="none">
            <circle cx="12" cy="12" r="9" stroke="#0B5C4E" strokeOpacity="0.2" strokeWidth="3"/>
            <path d="M21 12a9 9 0 0 0-9-9" stroke="#0B5C4E" strokeWidth="3" strokeLinecap="round"/>
          </svg>
        )}
        <div className="flex-1 min-w-0">
          <div className="font-display font-semibold text-[14px] text-brand-deep truncate">
            {error ? "Indexing failed" : done ? `Indexed “${job.filename}”` : `Indexing “${job.filename}”`}
          </div>
          <div className="text-[12px] text-muted">
            {error ? (job.error || "Something went wrong.") : (
              <>
                {PHASE_LABEL[job.phase] || "Working…"} · <b className="text-ink font-mono">{job.items_created}</b> product{job.items_created === 1 ? "" : "s"}
                {" · "}<b className="text-ink font-mono">{job.text_chunks}</b> text chunk{job.text_chunks === 1 ? "" : "s"}
              </>
            )}
          </div>
        </div>
      </div>
      {!error && (
        <div className="mt-3 h-1.5 rounded-full bg-brand/10 overflow-hidden">
          <div className={`h-full rounded-full bg-brand-deep transition-all duration-700 ${done ? "" : "animate-pulse"}`}
            style={{ width: done ? "100%" : pct != null ? `${Math.max(8, pct)}%` : "40%" }} />
        </div>
      )}
    </div>
  );
}

function SidebarCard({ title, children }) {
  return (
    <div className="bg-surface border border-hair rounded-xl p-4">
      <div className="font-display font-semibold text-[14px] mb-3">{title}</div>
      {children}
    </div>
  );
}

function EmptyState({ icon, title, hint }) {
  const paths = {
    box: <><path d="M21 8l-9-5-9 5v8l9 5 9-5z" strokeLinejoin="round"/><path d="M3 8l9 5 9-5M12 13v8" strokeLinejoin="round"/></>,
    file: <><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" strokeLinejoin="round"/><path d="M14 2v6h6" strokeLinejoin="round"/></>,
    book: <><path d="M4 19.5A2.5 2.5 0 016.5 17H20" strokeLinejoin="round"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 014 19.5v-15A2.5 2.5 0 016.5 2z" strokeLinejoin="round"/></>,
  };
  return (
    <div className="border border-dashed border-hair rounded-xl py-12 flex flex-col items-center text-center">
      <span className="w-11 h-11 rounded-xl bg-canvas flex items-center justify-center mb-3">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#9AA4B0" strokeWidth="1.6">{paths[icon]}</svg>
      </span>
      <div className="text-[13.5px] font-medium text-ink">{title}</div>
      <div className="text-[12px] text-muted mt-1 max-w-xs">{hint}</div>
    </div>
  );
}
