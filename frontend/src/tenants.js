// Per-tenant visual identity. The console re-themes to the active tenant's accent.
export const TENANT_THEME = {
  tenant_a: {
    accent: "#A66A2E",        // warm bronze — luxury furniture
    accentSoft: "#F2E9DC",
    initial: "L",
    kind: "Luxury Furniture",
    persona: "Aria · design concierge",
  },
  tenant_b: {
    accent: "#3E5C78",        // slate blue — automotive
    accentSoft: "#E9EEF3",
    initial: "A",
    kind: "Automotive Care",
    persona: "Max · service advisor",
  },
};

export const FALLBACK_THEME = {
  accent: "#2D5A4A",
  accentSoft: "#E8EFEA",
  initial: "•",
  kind: "Tenant",
  persona: "",
};

export const themeFor = (id) => TENANT_THEME[id] || FALLBACK_THEME;

export const STATUS = {
  WAITING_FOR_BOT: { label: "Bot active", dot: "#2D5A4A", text: "#1F4034", bg: "#E8EFEA" },
  AGENT_RESPONDING: { label: "Replying…", dot: "#2D5A4A", text: "#1F4034", bg: "#E8EFEA" },
  RESOLVED: { label: "Resolved", dot: "#5C7A52", text: "#3F5638", bg: "#ECF0E6" },
  NEEDS_HUMAN: { label: "Needs human", dot: "#C4543F", text: "#A23D2C", bg: "#F7E9E4" },
};

// Which statuses each dashboard filter shows.
export const STATUS_FILTERS = {
  active: ["WAITING_FOR_BOT", "AGENT_RESPONDING"], // open & bot-managed
  RESOLVED: ["RESOLVED"],
  NEEDS_HUMAN: ["NEEDS_HUMAN"],
};
