/** Drifting colour blobs + dot grid behind the glass. Purely decorative. */
export function AmbientBackground() {
  return (
    <div className="ambient" aria-hidden="true">
      <span className="blob" style={{ width: 520, height: 520, left: -120, top: -160, background: 'var(--blob-1)' }} />
      <span className="blob" style={{ width: 460, height: 460, right: -100, top: 200, background: 'var(--blob-2)', animationDelay: '-6s' }} />
      <span className="blob" style={{ width: 420, height: 420, left: '38%', bottom: -180, background: 'var(--blob-3)', animationDelay: '-12s' }} />
      <span className="dot-grid" />
    </div>
  );
}
