// PublicLibraryPage — discover lessons that other users marked public.
//
// Item #31. Fetches /api/public/recent and renders the result as cards. Each
// card links to /?share=<code> which the existing share-loading flow already
// handles.

import React, { useEffect, useState } from "react";
import { Globe, Loader2 } from "lucide-react";
import { C, SANS, BODY } from "../theme";
import { flaskBase } from "../lib/api";

interface PublicShare {
  code: string;
  title: string;
  scene: string | null;
  domain: string | null;
  created_at: number | null;
}

function relativeTime(ts: number | null): string {
  if (!ts) return "";
  const secs = Math.max(0, Math.floor(Date.now() / 1000 - ts));
  if (secs < 60) return "just now";
  if (secs < 3600) return `${Math.floor(secs / 60)}m ago`;
  if (secs < 86400) return `${Math.floor(secs / 3600)}h ago`;
  return `${Math.floor(secs / 86400)}d ago`;
}

export const PublicLibraryPage: React.FC = () => {
  const [shares, setShares] = useState<PublicShare[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch(`${flaskBase}/api/public/recent`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const json = await res.json();
        if (!cancelled) setShares(json.shares ?? []);
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : String(err));
      }
    })();
    return () => { cancelled = true; };
  }, []);

  return (
    <div
      className="h-full overflow-y-auto"
      style={{ background: C.bg, color: C.text, fontFamily: BODY }}
    >
      <div className="max-w-5xl mx-auto px-8 py-10">
        <header className="mb-8">
          <h1
            style={{
              fontFamily: SANS,
              fontSize: 32,
              fontWeight: 600,
              letterSpacing: "-0.02em",
              marginBottom: 8,
              display: "inline-flex",
              alignItems: "center",
              gap: 10,
            }}
          >
            <Globe size={26} strokeWidth={1.75} />
            Public lessons
          </h1>
          <p style={{ color: C.textMuted, fontSize: 14, lineHeight: 1.6 }}>
            Lessons that other users marked public. Click one to open it in
            the regular paste-problem view.
          </p>
        </header>

        {error && (
          <div
            className="p-3 rounded-md"
            style={{
              background: "rgba(239, 68, 68, 0.10)",
              border: "1px solid rgba(239, 68, 68, 0.35)",
              color: "#fca5a5",
              fontSize: 13,
            }}
          >
            Couldn't load public lessons: {error}
          </div>
        )}

        {!error && shares === null && (
          <div style={{ color: C.textFaint, fontSize: 14, display: "flex", alignItems: "center", gap: 8 }}>
            <Loader2 size={14} className="animate-spin" strokeWidth={2} />
            Loading…
          </div>
        )}

        {!error && shares !== null && shares.length === 0 && (
          <div style={{ color: C.textFaint, fontSize: 14 }}>
            No public lessons yet. Be the first — mark a share <em>public</em>
            when creating it.
          </div>
        )}

        {!error && shares && shares.length > 0 && (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {shares.map((s) => (
              <a
                key={s.code}
                href={`/?share=${encodeURIComponent(s.code)}`}
                className="rounded-md p-4 block"
                style={{
                  background: C.surface,
                  border: `1px solid ${C.borderAlt}`,
                  textDecoration: "none",
                  color: C.text,
                }}
              >
                <div
                  style={{
                    fontFamily: SANS,
                    fontSize: 15,
                    fontWeight: 600,
                    marginBottom: 6,
                  }}
                >
                  {s.title}
                </div>
                <div style={{ fontSize: 11, color: C.textFaint, display: "flex", gap: 8 }}>
                  {s.scene && <span>{s.scene}</span>}
                  {s.domain && (
                    <>
                      <span>·</span>
                      <span>{s.domain}</span>
                    </>
                  )}
                  {s.created_at && (
                    <>
                      <span>·</span>
                      <span>{relativeTime(s.created_at)}</span>
                    </>
                  )}
                </div>
              </a>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default PublicLibraryPage;
