import type { IconProps } from "@opal/types";
import { useId } from "react";

const SvgOnyxLogo = ({ size, ...props }: IconProps) => {
  const maskId = useId();

  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 512 512"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      role="img"
      aria-label="LKnow"
      {...props}
    >
      <mask
        id={maskId}
        maskUnits="userSpaceOnUse"
        style={{ maskType: "alpha" }}
      >
        <image
          href="/logo.png"
          width="512"
          height="512"
          preserveAspectRatio="xMidYMid meet"
        />
      </mask>
      <rect
        width="512"
        height="512"
        fill="currentColor"
        mask={`url(#${maskId})`}
      />
    </svg>
  );
};
export default SvgOnyxLogo;
