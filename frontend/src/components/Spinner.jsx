export default function Spinner({ size = 13, color = "currentColor" }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      role="img"
      aria-label="loading"
      style={{ display: "inline-block", verticalAlign: "-0.15em" }}
    >
      <circle cx="12" cy="12" r="9" fill="none" stroke={color} strokeOpacity="0.3" strokeWidth="3" />
      <path d="M12 3 a9 9 0 0 1 9 9" fill="none" stroke={color} strokeWidth="3" strokeLinecap="round">
        <animateTransform
          attributeName="transform"
          type="rotate"
          from="0 12 12"
          to="360 12 12"
          dur="0.7s"
          repeatCount="indefinite"
        />
      </path>
    </svg>
  );
}
