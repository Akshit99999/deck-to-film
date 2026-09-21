/**
 * Easing functions for animations.
 * All take t in [0,1] and return a value in [0,1].
 */

export const easeInOutCubic = (t: number): number =>
  t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;

export const easeOutCubic = (t: number): number => 1 - Math.pow(1 - t, 3);

export const easeInCubic = (t: number): number => t * t * t;

export const spring = (t: number, tension = 200, friction = 20): number => {
  // Critically damped spring approximation
  const w0 = Math.sqrt(tension);
  const zeta = friction / (2 * Math.sqrt(tension));
  if (zeta < 1) {
    const wd = w0 * Math.sqrt(1 - zeta * zeta);
    return (
      1 -
      Math.exp(-zeta * w0 * t) *
        (Math.cos(wd * t) + (zeta / Math.sqrt(1 - zeta * zeta)) * Math.sin(wd * t))
    );
  }
  return 1 - (1 + w0 * t) * Math.exp(-w0 * t);
};

/** Remap t from [inMin,inMax] to [outMin,outMax] clamped. */
export const remap = (
  t: number,
  inMin: number,
  inMax: number,
  outMin = 0,
  outMax = 1,
): number => {
  const clamped = Math.min(Math.max(t, inMin), inMax);
  return outMin + ((clamped - inMin) / (inMax - inMin)) * (outMax - outMin);
};
