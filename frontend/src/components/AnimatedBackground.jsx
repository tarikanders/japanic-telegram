import './AnimatedBackground.css'

/**
 * Fond animé légèrement flouté : 3 blobs en dégradé (violet/pink/teal)
 * en position fixed, animés lentement. Pur CSS, aucune lib.
 * Monté dans App.jsx derrière main-content.
 */
export default function AnimatedBackground() {
  return (
    <div className="anim-bg" aria-hidden="true">
      <div className="blob blob-1" />
      <div className="blob blob-2" />
      <div className="blob blob-3" />
      <div className="anim-bg-overlay" />
    </div>
  )
}
