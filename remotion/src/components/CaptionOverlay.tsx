/**
 * CaptionOverlay — renders burned-in captions from an SRT string.
 *
 * Features:
 *  - Word-by-word highlight of currently spoken word (accent color)
 *  - Safe-zone positioning (avoids demo UI at bottom)
 *  - WCAG AA contrast: white text on dark semi-transparent pill
 *  - Smooth fade-in per caption
 *  - Optional clean mode (no word highlight)
 */

import React from "react";
import { useCurrentFrame, useVideoConfig } from "remotion";
import { withAlpha } from "../lib/theme";
import { remap, easeOutCubic } from "../lib/easing";

interface SrtEntry {
  index: number;
  start: number; // seconds
  end: number;
  text: string;
  words: { word: string; start: number; end: number }[];
}

interface CaptionOverlayProps {
  srtContent: string;
  accentColor: string;
  /** If true, show captions higher up (demo scene has bottom UI) */
  liftForDemo?: boolean;
  cleanMode?: boolean;
  fontSize?: number;
}

function parseSrt(srt: string): SrtEntry[] {
  const entries: SrtEntry[] = [];
  const blocks = srt.trim().split(/\n\n+/);

  for (const block of blocks) {
    const lines = block.trim().split("\n");
    if (lines.length < 3) continue;

    const index = parseInt(lines[0], 10);
    const timeParts = lines[1].split(" --> ");
    const start = parseSrtTime(timeParts[0]);
    const end = parseSrtTime(timeParts[1]);
    const text = lines.slice(2).join(" ");
    const words = text.split(/\s+/).map((word) => ({
      word,
      // Distribute words evenly across the caption duration
      start: 0,
      end: 0,
    }));

    // Distribute word timings evenly within caption
    const wordDur = (end - start) / Math.max(words.length, 1);
    words.forEach((w, i) => {
      w.start = start + i * wordDur;
      w.end = start + (i + 1) * wordDur;
    });

    entries.push({ index, start, end, text, words });
  }
  return entries;
}

function parseSrtTime(s: string): number {
  const clean = s.trim().replace(",", ".");
  const [hms, ms] = clean.split(".");
  const parts = hms.split(":");
  const h = parseInt(parts[0], 10);
  const m = parseInt(parts[1], 10);
  const sec = parseInt(parts[2], 10);
  return h * 3600 + m * 60 + sec + parseFloat(`0.${ms || "0"}`);
}

export const CaptionOverlay: React.FC<CaptionOverlayProps> = ({
  srtContent,
  accentColor,
  liftForDemo = false,
  cleanMode = false,
  fontSize = 44,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const currentSecs = frame / fps;

  const entries = React.useMemo(() => parseSrt(srtContent), [srtContent]);

  const active = entries.find(
    (e) => currentSecs >= e.start && currentSecs <= e.end
  );

  if (!active) return null;

  // Fade in over first 6 frames
  const fadeProgress = remap(
    currentSecs,
    active.start,
    active.start + 6 / fps,
    0,
    1
  );
  const opacity = easeOutCubic(Math.min(fadeProgress, 1));

  const bottomOffset = liftForDemo ? 200 : 80;

  const lines = active.text.split("\n");

  const renderLine = (line: string, lineIdx: number) => {
    if (cleanMode) {
      return (
        <span key={lineIdx} style={{ display: "block" }}>
          {line}
        </span>
      );
    }

    const lineWords = line.split(/\s+/);
    let charOffset = 0;
    const lineStart = lineIdx === 0 ? 0 : lines[0].length + 1;

    return (
      <span key={lineIdx} style={{ display: "block" }}>
        {lineWords.map((word, wi) => {
          // Find this word in the words array
          const wordEntry = active.words.find(
            (w) => w.word.replace(/[^a-zA-Z0-9]/g, "") === word.replace(/[^a-zA-Z0-9]/g, "")
          );
          const isActive =
            wordEntry &&
            currentSecs >= wordEntry.start &&
            currentSecs <= wordEntry.end;

          return (
            <React.Fragment key={wi}>
              {wi > 0 && " "}
              <span
                style={{
                  color: isActive ? accentColor : "#f0f0ff",
                  fontWeight: isActive ? 700 : 600,
                  transition: "color 0.06s ease",
                }}
              >
                {word}
              </span>
            </React.Fragment>
          );
        })}
      </span>
    );
  };

  return (
    <div
      style={{
        position: "absolute",
        bottom: bottomOffset,
        left: "50%",
        transform: "translateX(-50%)",
        opacity,
        zIndex: 1000,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        gap: 4,
        maxWidth: "80%",
        textAlign: "center",
      }}
    >
      <div
        style={{
          background: "rgba(0,0,0,0.72)",
          borderRadius: 12,
          padding: "10px 28px",
          backdropFilter: "blur(4px)",
          boxShadow: "0 2px 24px rgba(0,0,0,0.5)",
        }}
      >
        <div
          style={{
            fontFamily: "Inter, sans-serif",
            fontSize,
            fontWeight: 600,
            color: "#f0f0ff",
            lineHeight: 1.3,
            letterSpacing: "0.01em",
            textShadow: "0 1px 4px rgba(0,0,0,0.8)",
          }}
        >
          {lines.map((line, i) => renderLine(line, i))}
        </div>
      </div>
    </div>
  );
};
