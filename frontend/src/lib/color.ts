/** Maps an OCR confidence value (0..1) to a semantic CSS color variable. */
export function getConfColor(conf: number): string {
  if (conf >= 0.9) return 'var(--color-success)';
  if (conf >= 0.7) return 'var(--color-warning)';
  return 'var(--color-danger)';
}
