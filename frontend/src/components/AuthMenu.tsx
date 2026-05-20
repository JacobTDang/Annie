// Auth menu — sign-in button + magic-link modal.
//
// Item #17 completion. Only rendered when `isAuthEnabled()` returns true,
// so projects without Supabase env vars see absolutely no auth UI.
//
// The Supabase SDK is lazy-loaded via the helpers in lib/auth.ts so this
// component contributes ~0 KB to the main chunk in anonymous builds.

import React, { useCallback, useEffect, useState } from "react";
import { LogIn, LogOut, Mail, X } from "lucide-react";
import {
  isAuthEnabled,
  getUser,
  signInWithEmail,
  signOut,
  type LumenUser,
} from "../lib/auth";
import { C, SANS, BODY } from "../theme";

export const AuthMenu: React.FC = () => {
  if (!isAuthEnabled()) return null;

  const [user, setUser] = useState<LumenUser | null>(null);
  const [open, setOpen] = useState(false);
  const [email, setEmail] = useState("");
  const [status, setStatus] = useState<"idle" | "sending" | "sent" | "error">("idle");

  useEffect(() => {
    let cancelled = false;
    getUser().then((u) => { if (!cancelled) setUser(u); });
    return () => { cancelled = true; };
  }, [open]);

  const handleSubmit = useCallback(async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email.trim()) return;
    setStatus("sending");
    const ok = await signInWithEmail(email.trim());
    setStatus(ok ? "sent" : "error");
  }, [email]);

  const handleSignOut = useCallback(async () => {
    await signOut();
    setUser(null);
    setOpen(false);
  }, []);

  return (
    <>
      <button
        onClick={() => setOpen(true)}
        aria-label={user ? "Account" : "Sign in"}
        style={{
          padding: "6px 12px",
          borderRadius: 4,
          border: `1px solid ${C.borderAlt}`,
          background: "transparent",
          color: C.text,
          fontSize: 12,
          cursor: "pointer",
          display: "inline-flex",
          alignItems: "center",
          gap: 6,
        }}
      >
        {user ? (
          <>
            <Mail size={12} strokeWidth={2} />
            <span style={{ maxWidth: 160, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
              {user.email ?? "Account"}
            </span>
          </>
        ) : (
          <>
            <LogIn size={12} strokeWidth={2} />
            Sign in
          </>
        )}
      </button>

      {open && (
        <div
          onClick={() => setOpen(false)}
          style={{
            position: "fixed",
            inset: 0,
            background: "rgba(0,0,0,0.7)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 50,
          }}
        >
          <div
            onClick={(e) => e.stopPropagation()}
            style={{
              width: "100%",
              maxWidth: 380,
              background: C.bg,
              border: `1px solid ${C.borderAlt}`,
              borderRadius: 8,
              padding: 24,
              position: "relative",
            }}
          >
            <button
              onClick={() => setOpen(false)}
              aria-label="Close"
              style={{
                position: "absolute",
                top: 10,
                right: 10,
                background: "transparent",
                border: "none",
                color: C.textMuted,
                cursor: "pointer",
              }}
            >
              <X size={18} strokeWidth={2} />
            </button>

            {user ? (
              <>
                <div style={{ fontFamily: SANS, fontSize: 16, fontWeight: 600, marginBottom: 4 }}>
                  Signed in
                </div>
                <div style={{ fontSize: 13, color: C.textMuted, marginBottom: 18 }}>
                  {user.email}
                </div>
                <button
                  onClick={handleSignOut}
                  style={{
                    padding: "8px 14px",
                    borderRadius: 4,
                    border: `1px solid ${C.borderAlt}`,
                    background: "transparent",
                    color: "#fca5a5",
                    fontSize: 13,
                    cursor: "pointer",
                    display: "inline-flex",
                    alignItems: "center",
                    gap: 6,
                  }}
                >
                  <LogOut size={12} strokeWidth={2} /> Sign out
                </button>
              </>
            ) : (
              <form onSubmit={handleSubmit}>
                <div style={{ fontFamily: SANS, fontSize: 16, fontWeight: 600, marginBottom: 4 }}>
                  Sign in with email
                </div>
                <div style={{ fontSize: 12, color: C.textMuted, marginBottom: 14 }}>
                  We'll send a one-time magic link — no password required.
                </div>
                <input
                  type="email"
                  required
                  placeholder="you@example.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  disabled={status === "sending"}
                  style={{
                    width: "100%",
                    padding: 10,
                    borderRadius: 4,
                    border: `1px solid ${C.borderAlt}`,
                    background: C.surface,
                    color: C.text,
                    fontSize: 14,
                    marginBottom: 12,
                  }}
                />
                <button
                  type="submit"
                  disabled={status === "sending" || !email.trim()}
                  style={{
                    width: "100%",
                    padding: "8px 14px",
                    borderRadius: 4,
                    border: "none",
                    background: status === "sending" ? C.borderAlt : C.accent,
                    color: "#fff",
                    fontSize: 13,
                    cursor: status === "sending" ? "not-allowed" : "pointer",
                  }}
                >
                  {status === "sending" ? "Sending…" : "Send magic link"}
                </button>
                {status === "sent" && (
                  <div style={{ marginTop: 10, fontSize: 12, color: C.ok }}>
                    Check your inbox — the link is on the way.
                  </div>
                )}
                {status === "error" && (
                  <div style={{ marginTop: 10, fontSize: 12, color: "#fca5a5" }}>
                    Couldn't send the email. Check your address and try again.
                  </div>
                )}
              </form>
            )}
          </div>
        </div>
      )}
    </>
  );
};

export default AuthMenu;
