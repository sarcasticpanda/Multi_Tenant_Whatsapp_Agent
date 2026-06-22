const TENANT_META = {
  tenant_a: { emoji: "🛋️", tagline: "Luxury Furniture", color: "from-amber-500 to-orange-600" },
  tenant_b: { emoji: "🔧", tagline: "Automotive Care", color: "from-blue-500 to-indigo-600" },
};

export default function TenantSwitcher({ tenants, activeTenant, onSelect }) {
  return (
    <div className="flex gap-3">
      {tenants.map((t) => {
        const meta = TENANT_META[t.tenant_id] || { emoji: "🏢", tagline: "", color: "from-gray-500 to-gray-700" };
        const active = activeTenant === t.tenant_id;
        return (
          <button
            key={t.tenant_id}
            onClick={() => onSelect(t.tenant_id)}
            className={`flex items-center gap-3 px-4 py-3 rounded-xl border-2 transition-all ${
              active
                ? `bg-gradient-to-r ${meta.color} text-white border-transparent shadow-lg scale-105`
                : "bg-white text-gray-700 border-gray-200 hover:border-gray-300"
            }`}
          >
            <span className="text-2xl">{meta.emoji}</span>
            <div className="text-left">
              <div className="font-semibold text-sm leading-tight">{t.name}</div>
              <div className={`text-xs ${active ? "text-white/80" : "text-gray-400"}`}>{meta.tagline}</div>
            </div>
          </button>
        );
      })}
    </div>
  );
}
