import { staticFile } from "remotion";

/**
 * Resolves any relative asset path to a Remotion staticFile URL.
 * Handles audio, slides, videos, etc.
 */
export function resolveAsset(src: string | undefined | null): string {
  if (!src) return "";
  if (
    src.startsWith("http://") ||
    src.startsWith("https://") ||
    src.startsWith("data:") ||
    src.startsWith("blob:")
  ) {
    return src;
  }
  const clean = src.replace(/^\/+/, "").replace(/^public\/+/, "");
  try {
    return staticFile(clean);
  } catch {
    return `/public/${clean}`;
  }
}
