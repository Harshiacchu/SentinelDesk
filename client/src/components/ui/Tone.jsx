/** Primitive coloured bits. `tone` is a severity level or 'info' | 'muted'. */
export const toneClass = (tone) => `tone-${tone ?? 'muted'}`;

export function Dot({ tone, glow, pulse, size = 8 }) {
  return <span className={`dot ${toneClass(tone)} ${glow ? 'dot-glow' : ''} ${pulse ? 'ping' : ''}`} style={{ width: size, height: size }} />;
}

export function Chip({ tone, children, className = '' }) {
  return <span className={`chip ${tone ? toneClass(tone) : ''} ${className}`}>{children}</span>;
}

export function ConfidenceBar({ value }) {
  return <span className="bar" role="img" aria-label={`${Math.round(value)} percent`}><span style={{ width: `${Math.max(2, value)}%` }} /></span>;
}
