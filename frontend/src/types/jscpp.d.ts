// Ambient type declaration for JSCPP — the package ships no .d.ts.
// Loose typing is fine: callers (runCpp.ts) wrap the actual call.

declare module "JSCPP" {
  export function run(code: string, input?: string, config?: any): any;
  const _default: { run: typeof run } | typeof run;
  export default _default;
}
