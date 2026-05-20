// Item #17 — optional Supabase auth.
//
// When Supabase env vars are present and `@supabase/supabase-js` is installed,
// users can sign in and the lib forwards their access token on API calls.
// When the env vars are missing OR the SDK isn't available, all helpers
// degrade gracefully — `getUser()` returns null and the rest of the app
// uses browser-local storage just like before.
//
// The Supabase client is loaded LAZILY (dynamic import) so the SDK doesn't
// touch the main bundle for users who never sign in.

export interface LumenUser {
  id: string;
  email: string | null;
}

let _client: any | null = null;
let _initPromise: Promise<any | null> | null = null;

function _env(key: string): string | undefined {
  // Vite exposes env vars on import.meta.env.VITE_*
  const meta: any = (import.meta as any).env ?? {};
  return meta[key];
}

/** True iff Supabase env vars are configured. */
export function isAuthEnabled(): boolean {
  return Boolean(_env("VITE_SUPABASE_URL") && _env("VITE_SUPABASE_ANON_KEY"));
}

/** Lazily initialize the Supabase client. Resolves to null if unavailable. */
export async function getClient(): Promise<any | null> {
  if (_client) return _client;
  if (_initPromise) return _initPromise;
  if (!isAuthEnabled()) return null;
  _initPromise = (async () => {
    try {
      // Dynamic import so the SDK is split into its own chunk. The path is
      // built at runtime via .join() so the TypeScript compiler doesn't try
      // to resolve `@supabase/supabase-js` at build time (the dep is opt-in
      // — projects that don't use auth shouldn't have to install it).
      const sdkPath = ["@supabase", "supabase-js"].join("/");
      const mod: any = await import(/* @vite-ignore */ sdkPath);
      _client = mod.createClient(
        _env("VITE_SUPABASE_URL"),
        _env("VITE_SUPABASE_ANON_KEY"),
      );
      return _client;
    } catch (err) {
      // SDK not installed — silently disable. The Lumen contract is that
      // auth is OPTIONAL; missing SDK means anonymous mode, not an error.
      console.info("[auth] @supabase/supabase-js not installed — running anonymous");
      return null;
    }
  })();
  return _initPromise;
}

/** Get the currently signed-in user (or null). */
export async function getUser(): Promise<LumenUser | null> {
  const client = await getClient();
  if (!client) return null;
  try {
    const { data } = await client.auth.getUser();
    if (!data?.user) return null;
    return { id: data.user.id, email: data.user.email ?? null };
  } catch {
    return null;
  }
}

/** Return the current access token to attach to API requests (Bearer header). */
export async function getAccessToken(): Promise<string | null> {
  const client = await getClient();
  if (!client) return null;
  try {
    const { data } = await client.auth.getSession();
    return data?.session?.access_token ?? null;
  } catch {
    return null;
  }
}

/** Magic-link sign-in via email. Resolves to true on send, false on failure. */
export async function signInWithEmail(email: string): Promise<boolean> {
  const client = await getClient();
  if (!client) return false;
  try {
    const { error } = await client.auth.signInWithOtp({ email });
    return !error;
  } catch {
    return false;
  }
}

/** Sign out the current user (no-op when anonymous). */
export async function signOut(): Promise<void> {
  const client = await getClient();
  if (!client) return;
  try { await client.auth.signOut(); } catch { /* ignore */ }
}
