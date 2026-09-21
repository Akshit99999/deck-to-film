/**
 * ArchitectureScene — animated abstract nodes and edges.
 * Shows the product's high-level architecture visually, NO CODE.
 */

import React from "react";
import { useCurrentFrame, useVideoConfig, Audio } from "remotion";
import { spring, remap, easeOutCubic } from "../lib/easing";
import { withAlpha } from "../lib/theme";
import type { SceneProps } from "./types";

interface Node {
  id: string;
  label: string;
  x: number;
  y: number;
  isMain?: boolean;
}

interface Edge {
  from: string;
  to: string;
}

const DEFAULT_NODES: Node[] = [
  { id: "user", label: "User", x: 180, y: 300, isMain: false },
  { id: "app", label: "App", x: 520, y: 200, isMain: true },
  { id: "api", label: "API", x: 520, y: 400, isMain: true },
  { id: "db", label: "Database", x: 860, y: 300, isMain: false },
  { id: "cdn", label: "CDN", x: 860, y: 120, isMain: false },
];

const DEFAULT_EDGES: Edge[] = [
  { from: "user", to: "app" },
  { from: "user", to: "api" },
  { from: "app", to: "db" },
  { from: "api", to: "db" },
  { from: "app", to: "cdn" },
];

export const ArchitectureScene: React.FC<SceneProps> = ({
  scene,
  theme,
  durationFrames,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const headingProgress = easeOutCubic(remap(frame, 0, fps * 0.5, 0, 1));

  // Use bullets as node labels if we have 4-6 of them
  const nodes: Node[] =
    scene.bullets.length >= 3
      ? scene.bullets.slice(0, 5).map((label, i) => ({
          id: `node_${i}`,
          label,
          x: 180 + (i % 3) * 340,
          y: 180 + Math.floor(i / 3) * 220,
          isMain: i === Math.floor(scene.bullets.length / 2),
        }))
      : DEFAULT_NODES;

  const edges: Edge[] =
    nodes.length >= 2
      ? nodes.slice(1).map((n, i) => ({ from: nodes[i].id, to: n.id }))
      : DEFAULT_EDGES;

  const canvasW = 1040;
  const canvasH = 540;

  return (
    <div
      style={{
        position: "absolute",
        inset: 0,
        background: theme.bg,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        gap: 40,
        overflow: "hidden",
      }}
    >
      <h2
        style={{
          fontFamily: theme.fontHeading,
          fontSize: 56,
          fontWeight: 800,
          color: theme.text,
          opacity: headingProgress,
          letterSpacing: "-0.02em",
          margin: 0,
        }}
      >
        {scene.heading}
      </h2>

      {/* Node graph */}
      <svg width={canvasW} height={canvasH} style={{ overflow: "visible" }}>
        {/* Edges */}
        {edges.map((edge, i) => {
          const fromNode = nodes.find((n) => n.id === edge.from);
          const toNode = nodes.find((n) => n.id === edge.to);
          if (!fromNode || !toNode) return null;

          const delay = fps * (0.3 + i * 0.1);
          const ep = Math.min(Math.max((frame - delay) / (fps * 0.4), 0), 1);
          const ex = fromNode.x + (toNode.x - fromNode.x) * ep;
          const ey = fromNode.y + (toNode.y - fromNode.y) * ep;

          return (
            <g key={i}>
              <line
                x1={fromNode.x}
                y1={fromNode.y}
                x2={ex}
                y2={ey}
                stroke={withAlpha(theme.accent, 0.5)}
                strokeWidth={2}
                strokeDasharray="6 4"
              />
              {/* Animated particle along edge */}
              {ep >= 0.99 && (
                <circle
                  cx={
                    fromNode.x +
                    (toNode.x - fromNode.x) *
                      ((frame * 0.012 + i * 0.3) % 1)
                  }
                  cy={
                    fromNode.y +
                    (toNode.y - fromNode.y) *
                      ((frame * 0.012 + i * 0.3) % 1)
                  }
                  r={4}
                  fill={theme.accent}
                  style={{ filter: `drop-shadow(0 0 6px ${theme.accent})` }}
                />
              )}
            </g>
          );
        })}

        {/* Nodes */}
        {nodes.map((node, i) => {
          const delay = fps * (0.2 + i * 0.15);
          const np = spring(Math.max(0, (frame - delay) / fps), 180, 16);
          const nodeR = node.isMain ? 54 : 40;

          return (
            <g key={node.id} style={{ transform: `scale(${np})`, transformOrigin: `${node.x}px ${node.y}px` }}>
              {/* Glow */}
              <circle
                cx={node.x}
                cy={node.y}
                r={nodeR + 12}
                fill={withAlpha(theme.accent, node.isMain ? 0.15 : 0.06)}
              />
              {/* Body */}
              <circle
                cx={node.x}
                cy={node.y}
                r={nodeR}
                fill={node.isMain ? withAlpha(theme.accent, 0.3) : withAlpha("#ffffff", 0.06)}
                stroke={node.isMain ? theme.accent : withAlpha(theme.accent, 0.4)}
                strokeWidth={node.isMain ? 3 : 1.5}
              />
              {/* Label */}
              <text
                x={node.x}
                y={node.y + 6}
                textAnchor="middle"
                fill={node.isMain ? theme.text : theme.textMuted}
                fontFamily="Inter, sans-serif"
                fontSize={node.isMain ? 17 : 15}
                fontWeight={node.isMain ? 700 : 500}
              >
                {node.label.length > 12 ? node.label.slice(0, 11) + "…" : node.label}
              </text>
            </g>
          );
        })}
      </svg>

      {scene.audio_path && <Audio src={scene.audio_path} />}
    </div>
  );
};
