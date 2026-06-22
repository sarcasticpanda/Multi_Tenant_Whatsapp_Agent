import { useState } from "react";
import { login } from "../api/client";

export default function Login({ onSuccess }) {
  const [password, setPassword] = useState("");
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true); setError(null);
    try {
      await login(password);
      onSuccess();
    } catch {
      setError("Incorrect password. Try again.");
      setBusy(false);
    }
  };

  return (
    <div className="h-full flex items-center justify-center bg-rail">
      <form onSubmit={submit} className="w-[340px] bg-surface rounded-2xl shadow-lift p-7">
        <div className="w-11 h-11 rounded-xl bg-brand flex items-center justify-center mb-5">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none">
            <path d="M12 2a10 10 0 00-8.7 14.9L2 22l5.3-1.4A10 10 0 1012 2z" stroke="#fff" strokeWidth="1.6"/>
            <circle cx="9" cy="12" r="1.3" fill="#fff"/><circle cx="12" cy="12" r="1.3" fill="#fff"/><circle cx="15" cy="12" r="1.3" fill="#fff"/>
          </svg>
        </div>
        <h1 className="font-display text-[20px] font-semibold">Agent Console</h1>
        <p className="text-[13px] text-muted mt-1 mb-5">Sign in to monitor and manage your WhatsApp agents.</p>

        <label className="text-[11px] font-semibold text-faint uppercase tracking-wider">Admin password</label>
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          autoFocus
          placeholder="••••••••"
          className="w-full mt-1 text-[14px] border border-hair rounded-lg px-3 py-2.5 focus:outline-none focus:border-brand"
        />
        {error && <div className="text-[12px] text-alert mt-2">{error}</div>}
        <button
          type="submit"
          disabled={busy || !password}
          className="w-full mt-5 accent-bg text-white font-medium text-[14px] py-2.5 rounded-lg disabled:opacity-40"
        >
          {busy ? "Signing in…" : "Sign in"}
        </button>

        {/* Demo convenience: prefill the reviewer password in one tap */}
        <button
          type="button"
          onClick={() => setPassword("kredai_admin")}
          className="w-full mt-3 text-[12px] text-muted hover:text-ink transition-colors"
        >
          Reviewer demo? Password: <span className="font-mono text-ink">kredai_admin</span> — tap to fill
        </button>
      </form>
    </div>
  );
}
