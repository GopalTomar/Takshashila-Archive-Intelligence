// Takshashila lighthouse mark, reconstructed as inline SVG from the provided
// brand logo. Colours are the brand tokens: wine #620d3c and marigold #f1a222.
export function Logo({ size = 40 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 120 120" fill="none" role="img" aria-label="Takshashila">
      <circle cx="60" cy="60" r="44" fill="#f1a222" />
      {/* light beam */}
      <path d="M60 44 L20 34 L20 58 Z" fill="#ffd100" opacity="0.9" />
      <path d="M60 44 L100 34 L100 52 Z" fill="#ffd100" opacity="0.55" />
      {/* lighthouse */}
      <g fill="#620d3c">
        <rect x="56.5" y="26" width="7" height="6" />
        <path d="M50 34 h20 l-4 8 h-12 z" />
        <rect x="52" y="42" width="16" height="12" />
        <path d="M53 54 L67 54 L72 96 L48 96 Z" />
      </g>
      {/* lit windows */}
      <g fill="#ffd100">
        <rect x="54.5" y="44" width="3" height="8" />
        <rect x="58.5" y="44" width="3" height="8" />
        <rect x="62.5" y="44" width="3" height="8" />
        <rect x="58" y="62" width="4" height="8" rx="2" />
      </g>
    </svg>
  );
}
