// Accent-color presets used by Tweaks.
export const ACCENT_PRESETS = {
  '#2dd4a4': { deep: '#0f9b76', soft: '#d6f5ea' },   // jade (default)
  '#f97316': { deep: '#c2410c', soft: '#ffedd5' },   // orange
  '#3b82f6': { deep: '#1d4ed8', soft: '#dbeafe' },   // blue
  '#a855f7': { deep: '#7e22ce', soft: '#f3e8ff' },   // violet
  '#facc15': { deep: '#a16207', soft: '#fef9c3' },   // yellow
  '#0a0a0a': { deep: '#0a0a0a', soft: '#e7e5e4' },   // mono
};

export function deriveAccent(hex) {
  if (ACCENT_PRESETS[hex]) return ACCENT_PRESETS[hex];
  return { deep: hex, soft: hex + '22' };
}
