import type { IconProps } from "@opal/types";
const SvgOnyxTyped = ({ size, ...props }: IconProps) => (
  <svg
    width={size != null ? size * 3.4 : undefined}
    height={size}
    viewBox="0 0 218 64"
    fill="none"
    xmlns="http://www.w3.org/2000/svg"
    role="img"
    aria-label="LKnow"
    {...props}
  >
    <text
      x="0"
      y="47"
      fill="currentColor"
      fontFamily='"Hanken Grotesk", "Inter", "Segoe UI", system-ui, sans-serif'
      fontSize="48"
      fontWeight="700"
      letterSpacing="0"
    >
      LKnow
    </text>
  </svg>
);
export default SvgOnyxTyped;
