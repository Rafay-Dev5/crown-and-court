/** Shared player-facing copy helpers. */

export function cardNoun(n: unknown): string {
  const c = Number(n) || 0;
  return c === 1 ? "1 card" : `${c} cards`;
}

export function roundNoun(n: unknown): string {
  const c = Number(n) || 0;
  return c === 1 ? "1 round" : `${c} rounds`;
}

export function sentence(text: string): string {
  const t = text.trim();
  if (!t) return t;
  return t.charAt(0).toUpperCase() + t.slice(1);
}

export function eventFingerprint(e: Record<string, unknown>): string {
  return JSON.stringify(e);
}
