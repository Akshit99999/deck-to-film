/**
 * DeviceFrame — renders recorded demo footage inside a 3D browser or phone frame.
 *
 * Uses @remotion/three + Three.js for PBR materials, soft shadows, reflections.
 * Camera drifts gently during idle, settles flat-on during interactions.
 */

import React, { useRef } from "react";
import { useCurrentFrame, useVideoConfig, Video } from "remotion";
import { ThreeCanvas } from "@remotion/three";
import * as THREE from "three";
import { remap, easeInOutCubic } from "../lib/easing";

interface ActionEvent {
  timestamp_ms: number;
  action: string;
  x: number;
  y: number;
  width: number;
  height: number;
  narration_cue: string;
}

interface DeviceFrameProps {
  videoSrc: string;
  deviceType: "laptop" | "phone";
  actions: ActionEvent[];
  accentColor: string;
  /** Duration of this scene in frames */
  durationFrames: number;
}

const LAPTOP_ASPECT = 16 / 10;
const PHONE_ASPECT = 9 / 19.5;

export const DeviceFrame: React.FC<DeviceFrameProps> = ({
  videoSrc,
  deviceType,
  actions,
  accentColor,
  durationFrames,
}) => {
  const frame = useCurrentFrame();
  const { fps, width, height } = useVideoConfig();
  const currentMs = (frame / fps) * 1000;

  // Find the closest upcoming action for zoom target
  const activeAction = actions
    .filter((a) => Math.abs(a.timestamp_ms - currentMs) < 2000)
    .sort((a, b) => Math.abs(a.timestamp_ms - currentMs) - Math.abs(b.timestamp_ms - currentMs))[0];

  // Camera drift: slow orbit during idle, settle on action
  const idleT = (frame % (fps * 8)) / (fps * 8); // 8s orbit cycle
  const isInteracting = activeAction && Math.abs(activeAction.timestamp_ms - currentMs) < 800;

  const cameraX = isInteracting ? 0 : Math.sin(idleT * Math.PI * 2) * 0.15;
  const cameraY = isInteracting ? 0 : Math.cos(idleT * Math.PI) * 0.05;
  const cameraZ = isInteracting ? 3.5 : 3.8;

  return (
    <div style={{ position: "absolute", inset: 0 }}>
      {/* The video playing in the background at reduced opacity */}
      <div
        style={{
          position: "absolute",
          inset: 0,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        <ThreeCanvas
          width={width}
          height={height}
          style={{ position: "absolute", inset: 0 }}
        >
          <DeviceScene
            videoSrc={videoSrc}
            deviceType={deviceType}
            cameraX={cameraX}
            cameraY={cameraY}
            cameraZ={cameraZ}
            accentColor={accentColor}
          />
        </ThreeCanvas>
      </div>

      {/* Zoom overlay: crop + enlarge the action region */}
      {activeAction && isInteracting && (
        <ZoomOverlay
          action={activeAction}
          videoWidth={1920}
          videoHeight={1080}
          overlayWidth={width}
          overlayHeight={height}
          currentMs={currentMs}
        />
      )}
    </div>
  );
};

// ---------------------------------------------------------------------------
// Three.js Scene
// ---------------------------------------------------------------------------

const DeviceScene: React.FC<{
  videoSrc: string;
  deviceType: "laptop" | "phone";
  cameraX: number;
  cameraY: number;
  cameraZ: number;
  accentColor: string;
}> = ({ videoSrc, deviceType, cameraX, cameraY, cameraZ, accentColor }) => {
  const isPhone = deviceType === "phone";
  const aspect = isPhone ? PHONE_ASPECT : LAPTOP_ASPECT;
  const screenW = isPhone ? 1.2 : 3.0;
  const screenH = screenW / aspect;

  return (
    <>
      {/* Environment lighting */}
      <ambientLight intensity={0.4} />
      <directionalLight
        position={[5, 8, 5]}
        intensity={1.2}
        castShadow
        shadow-mapSize={[2048, 2048]}
      />
      <pointLight position={[-4, 2, 4]} intensity={0.6} color={accentColor} />

      {/* Camera */}
      <perspectiveCamera
        makeDefault
        position={[cameraX, cameraY, cameraZ]}
        fov={40}
      />

      {/* Device body */}
      <DeviceBody
        isPhone={isPhone}
        screenW={screenW}
        screenH={screenH}
        accentColor={accentColor}
      />

      {/* Subtle ground reflection */}
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -screenH / 2 - 0.3, 0]} receiveShadow>
        <planeGeometry args={[12, 12]} />
        <meshStandardMaterial color="#050508" roughness={0.1} metalness={0.3} />
      </mesh>
    </>
  );
};

const DeviceBody: React.FC<{
  isPhone: boolean;
  screenW: number;
  screenH: number;
  accentColor: string;
}> = ({ isPhone, screenW, screenH, accentColor }) => {
  const bezel = 0.08;
  const bodyW = screenW + bezel * 2;
  const bodyH = screenH + bezel * 2;
  const bodyD = isPhone ? 0.08 : 0.12;
  const cornerR = isPhone ? 0.15 : 0.06;

  return (
    <group>
      {/* Body */}
      <mesh castShadow receiveShadow>
        <boxGeometry args={[bodyW, bodyH, bodyD]} />
        <meshPhysicalMaterial
          color="#1a1a2e"
          roughness={0.3}
          metalness={0.7}
          reflectivity={0.8}
        />
      </mesh>

      {/* Screen glass */}
      <mesh position={[0, 0, bodyD / 2 + 0.001]}>
        <planeGeometry args={[screenW, screenH]} />
        <meshPhysicalMaterial
          color="#000"
          roughness={0.05}
          metalness={0.1}
          transmission={0.15}
          transparent
          opacity={0.95}
        />
      </mesh>

      {/* Accent glow rim */}
      <mesh position={[0, 0, -bodyD / 2 - 0.001]}>
        <planeGeometry args={[bodyW + 0.02, bodyH + 0.02]} />
        <meshBasicMaterial color={accentColor} transparent opacity={0.15} />
      </mesh>

      {/* Laptop hinge / base */}
      {!isPhone && (
        <group position={[0, -bodyH / 2 - 0.05, -0.2]} rotation={[-0.2, 0, 0]}>
          <mesh castShadow>
            <boxGeometry args={[bodyW, 0.08, 2.4]} />
            <meshPhysicalMaterial color="#1a1a2e" roughness={0.3} metalness={0.7} />
          </mesh>
        </group>
      )}
    </group>
  );
};

// ---------------------------------------------------------------------------
// Zoom overlay
// ---------------------------------------------------------------------------

const ZoomOverlay: React.FC<{
  action: ActionEvent;
  videoWidth: number;
  videoHeight: number;
  overlayWidth: number;
  overlayHeight: number;
  currentMs: number;
}> = ({ action, videoWidth, videoHeight, overlayWidth, overlayHeight, currentMs }) => {
  const pad = 60;
  const regionX = Math.max(0, action.x - pad);
  const regionY = Math.max(0, action.y - pad);
  const regionW = Math.min(action.width + pad * 2, videoWidth - regionX);
  const regionH = Math.min(action.height + pad * 2, videoHeight - regionY);

  // Scale to fit in a corner
  const previewW = overlayWidth * 0.35;
  const previewH = (regionH / regionW) * previewW;

  const progress = remap(currentMs, action.timestamp_ms - 300, action.timestamp_ms + 300, 0, 1);
  const scale = 0.8 + easeInOutCubic(Math.min(progress, 1)) * 0.2;

  return (
    <div
      style={{
        position: "absolute",
        bottom: 160,
        right: 40,
        width: previewW,
        height: previewH,
        border: "3px solid rgba(99,102,241,0.7)",
        borderRadius: 12,
        overflow: "hidden",
        transform: `scale(${scale})`,
        transformOrigin: "bottom right",
        boxShadow: "0 8px 48px rgba(0,0,0,0.6)",
      }}
    >
      <div
        style={{
          width: (videoWidth / regionW) * previewW,
          height: (videoHeight / regionH) * previewH,
          transform: `translate(${-(regionX / videoWidth) * (videoWidth / regionW) * previewW}px, ${-(regionY / videoHeight) * (videoHeight / regionH) * previewH}px)`,
        }}
      >
        {/* Label callout */}
        <div
          style={{
            position: "absolute",
            top: (regionY / videoHeight) * (videoHeight / regionH) * previewH + 4,
            left: (regionX / videoWidth) * (videoWidth / regionW) * previewW + 4,
            background: "rgba(99,102,241,0.85)",
            color: "#fff",
            fontSize: 13,
            fontWeight: 700,
            borderRadius: 6,
            padding: "2px 8px",
            fontFamily: "Inter, sans-serif",
            whiteSpace: "nowrap",
          }}
        >
          {action.narration_cue.split(" ").slice(0, 4).join(" ")}
        </div>
      </div>
    </div>
  );
};
