// PrereqGraphPage — Item #35.
//
// Static layered SVG graph: depth (longest path from a root) maps to Y;
// horizontal slot maps to X. No d3 / no react-flow — keeps the bundle small.
// Click a node to expand its prereq chain in a side panel.

import React, { useEffect, useMemo, useState } from "react";
import { Loader2 } from "lucide-react";
import { C, SANS, BODY } from "../theme";
import { flaskBase } from "../lib/api";

interface PrereqGraph {
  domains: Record<string, Record<string, string[]>>;
}

interface NodeLayout {
  id: string;
  domain: string;
  depth: number;
  slot: number;
  prereqs: string[];
}

// ─────────────────────────────────────────────────────────────────────────────
// Layout — depth = longest path from a root; nodes at the same depth get
// horizontal slots, evenly spaced.
// ─────────────────────────────────────────────────────────────────────────────

function layout(domain: string, edges: Record<string, string[]>): NodeLayout[] {
  const depth: Record<string, number> = {};
  const memo: Record<string, number> = {};

  function dfs(node: string, stack: Set<string>): number {
    if (memo[node] !== undefined) return memo[node];
    if (stack.has(node)) {
      // Cycle — bail; treat as depth 0 to avoid infinite recursion
      return 0;
    }
    const prereqs = edges[node] ?? [];
    if (prereqs.length === 0) {
      memo[node] = 0;
      return 0;
    }
    stack.add(node);
    let d = 0;
    for (const p of prereqs) {
      d = Math.max(d, 1 + dfs(p, stack));
    }
    stack.delete(node);
    memo[node] = d;
    return d;
  }

  for (const node of Object.keys(edges)) depth[node] = dfs(node, new Set());

  // Bucket nodes by depth, then assign slots alphabetically for determinism
  const byDepth: Record<number, string[]> = {};
  for (const [node, d] of Object.entries(depth)) {
    (byDepth[d] ??= []).push(node);
  }
  for (const arr of Object.values(byDepth)) arr.sort();

  const out: NodeLayout[] = [];
  for (const [d, nodes] of Object.entries(byDepth)) {
    nodes.forEach((id, i) => {
      out.push({
        id, domain,
        depth: Number(d),
        slot: i,
        prereqs: edges[id] ?? [],
      });
    });
  }
  return out;
}

// SVG sizing — generous to fit even the longest chain
const NODE_W = 140;
const NODE_H = 32;
const COL_GAP = 24;
const ROW_GAP = 60;

function svgPos(node: NodeLayout, slotCount: number): { x: number; y: number } {
  // Center each depth row horizontally
  const totalW = slotCount * (NODE_W + COL_GAP);
  const startX = -totalW / 2 + (NODE_W + COL_GAP) / 2;
  return {
    x: startX + node.slot * (NODE_W + COL_GAP),
    y: node.depth * ROW_GAP,
  };
}


export const PrereqGraphPage: React.FC = () => {
  const [graph, setGraph] = useState<PrereqGraph | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [activeDomain, setActiveDomain] = useState<string>("calculus");

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch(`${flaskBase}/api/prereqs`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const json: PrereqGraph = await res.json();
        if (!cancelled) {
          setGraph(json);
          // Pick a domain that has nodes
          const firstDomain = Object.keys(json.domains)[0];
          if (firstDomain) setActiveDomain(firstDomain);
        }
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : String(err));
      }
    })();
    return () => { cancelled = true; };
  }, []);

  const nodes = useMemo<NodeLayout[]>(() => {
    if (!graph) return [];
    const edges = graph.domains[activeDomain] ?? {};
    return layout(activeDomain, edges);
  }, [graph, activeDomain]);

  const slotCounts = useMemo(() => {
    const m: Record<number, number> = {};
    for (const n of nodes) m[n.depth] = Math.max(m[n.depth] ?? 0, n.slot + 1);
    return m;
  }, [nodes]);

  const maxSlots = useMemo(
    () => Math.max(1, ...Object.values(slotCounts)),
    [slotCounts],
  );

  const svgWidth = Math.max(800, maxSlots * (NODE_W + COL_GAP) + 80);
  const svgHeight = Math.max(400,
    (Math.max(0, ...nodes.map((n) => n.depth)) + 1) * ROW_GAP + NODE_H + 60,
  );

  return (
    <div
      className="h-full overflow-y-auto"
      style={{ background: C.bg, color: C.text, fontFamily: BODY }}
    >
      <div className="max-w-6xl mx-auto px-8 py-10">
        <header className="mb-6">
          <h1
            style={{
              fontFamily: SANS,
              fontSize: 32,
              fontWeight: 600,
              letterSpacing: "-0.02em",
              marginBottom: 8,
            }}
          >
            Prerequisites
          </h1>
          <p style={{ color: C.textMuted, fontSize: 14, lineHeight: 1.6 }}>
            Hand-curated map of which scenes build on which. Topics lower in
            the graph depend on topics above them.
          </p>
        </header>

        {error && (
          <div
            className="p-3 rounded-md mb-4"
            style={{
              background: "rgba(239, 68, 68, 0.10)",
              border: "1px solid rgba(239, 68, 68, 0.35)",
              color: "#fca5a5",
              fontSize: 13,
            }}
          >
            Couldn't load prerequisites: {error}
          </div>
        )}

        {!graph && !error && (
          <div style={{ color: C.textFaint, fontSize: 14, display: "inline-flex", alignItems: "center", gap: 8 }}>
            <Loader2 size={14} className="animate-spin" strokeWidth={2} /> Loading…
          </div>
        )}

        {graph && (
          <>
            <div className="flex gap-2 mb-4">
              {Object.keys(graph.domains).map((d) => (
                <button
                  key={d}
                  onClick={() => { setActiveDomain(d); setSelected(null); }}
                  style={{
                    padding: "6px 14px",
                    borderRadius: 4,
                    border: `1px solid ${activeDomain === d ? C.accent : C.borderAlt}`,
                    background: activeDomain === d ? C.accent : "transparent",
                    color: activeDomain === d ? "#fff" : C.text,
                    fontSize: 13,
                    cursor: "pointer",
                    textTransform: "capitalize",
                  }}
                >
                  {d}
                </button>
              ))}
            </div>

            <div
              className="rounded-md overflow-auto"
              style={{
                border: `1px solid ${C.borderAlt}`,
                background: C.surface,
                padding: 16,
              }}
            >
              <svg
                width={svgWidth}
                height={svgHeight}
                viewBox={`${-svgWidth / 2} -20 ${svgWidth} ${svgHeight}`}
                style={{ display: "block", margin: "0 auto" }}
              >
                {/* Edges first so nodes sit on top */}
                {nodes.flatMap((n) =>
                  n.prereqs.map((p) => {
                    const target = nodes.find((x) => x.id === p);
                    if (!target) return null;
                    const a = svgPos(n, slotCounts[n.depth]);
                    const b = svgPos(target, slotCounts[target.depth]);
                    return (
                      <line
                        key={`${n.id}->${p}`}
                        x1={a.x + NODE_W / 2}
                        y1={a.y}
                        x2={b.x + NODE_W / 2}
                        y2={b.y + NODE_H}
                        stroke={C.borderAlt}
                        strokeWidth={1.2}
                      />
                    );
                  })
                )}
                {nodes.map((n) => {
                  const { x, y } = svgPos(n, slotCounts[n.depth]);
                  const isActive = selected === n.id;
                  return (
                    <g
                      key={n.id}
                      transform={`translate(${x}, ${y})`}
                      onClick={() => setSelected(n.id)}
                      style={{ cursor: "pointer" }}
                    >
                      <rect
                        width={NODE_W}
                        height={NODE_H}
                        rx={4}
                        fill={isActive ? C.accent : C.bg}
                        stroke={isActive ? C.accent : C.borderAlt}
                        strokeWidth={1.5}
                      />
                      <text
                        x={NODE_W / 2}
                        y={NODE_H / 2 + 4}
                        textAnchor="middle"
                        fontSize={12}
                        fill={isActive ? "#fff" : C.text}
                        style={{ fontFamily: "ui-monospace, monospace" }}
                      >
                        {n.id}
                      </text>
                    </g>
                  );
                })}
              </svg>
            </div>

            {selected && (
              <div
                className="mt-4 p-4 rounded-md"
                style={{
                  background: C.surface,
                  border: `1px solid ${C.borderAlt}`,
                }}
              >
                <div style={{ fontFamily: SANS, fontWeight: 600, fontSize: 14, marginBottom: 8 }}>
                  {selected}
                </div>
                <div style={{ fontSize: 12, color: C.textMuted }}>
                  Prereqs:
                  {(graph.domains[activeDomain]?.[selected] ?? []).length === 0 ? (
                    <span style={{ color: C.textFaint, marginLeft: 6 }}>
                      None — foundational topic.
                    </span>
                  ) : (
                    <span style={{ marginLeft: 6 }}>
                      {(graph.domains[activeDomain]?.[selected] ?? []).join(", ")}
                    </span>
                  )}
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
};

export default PrereqGraphPage;
