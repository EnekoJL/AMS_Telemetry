/**
 * Speed-to-Color gradient for motorsport track visualization.
 * Neon Racing Green -> Electric Lime -> Gold -> Hot Racing Pink (No blues).
 */

const COLOR_STOPS = [
  { pos: 0.00, r: 0,   g: 170, b: 75  }, // Deep Green (Slow / Heavy braking)
  { pos: 0.25, r: 0,   g: 230, b: 118 }, // Racing Mint
  { pos: 0.50, r: 0,   g: 255, b: 136 }, // Neon Green (Mid speed)
  { pos: 0.75, r: 245, g: 220, b: 0   }, // Electric Lime / Gold
  { pos: 1.00, r: 255, g: 0,   b: 127 }, // Hot Racing Pink (Top speed / High-speed straight)
];

export function speedToColor(speedKmh, minSpeedKmh = 0, maxSpeedKmh = 350) {
  const range = maxSpeedKmh - minSpeedKmh;
  const t = range > 0 ? Math.max(0, Math.min(1, (speedKmh - minSpeedKmh) / range)) : 0.5;

  let lower = COLOR_STOPS[0];
  let upper = COLOR_STOPS[COLOR_STOPS.length - 1];

  for (let i = 0; i < COLOR_STOPS.length - 1; i++) {
    if (t >= COLOR_STOPS[i].pos && t <= COLOR_STOPS[i + 1].pos) {
      lower = COLOR_STOPS[i];
      upper = COLOR_STOPS[i + 1];
      break;
    }
  }

  const span = upper.pos - lower.pos;
  const factor = span > 0 ? (t - lower.pos) / span : 0;

  const r = Math.round(lower.r + factor * (upper.r - lower.r));
  const g = Math.round(lower.g + factor * (upper.g - lower.g));
  const b = Math.round(lower.b + factor * (upper.b - lower.b));

  return `rgb(${r}, ${g}, ${b})`;
}
