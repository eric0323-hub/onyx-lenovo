import { Interactive, type InteractiveStatelessProps } from "@opal/core";
import type {
  ContainerSizeVariants,
  ExtremaSizeVariants,
  RichStr,
} from "@opal/types";
import { Text, type TooltipSide, Tooltip } from "@opal/components";
import type { IconFunctionComponent } from "@opal/types";
import {
  iconVariants,
  iconWrapper,
} from "@opal/components/buttons/icon-wrapper";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type ButtonContentProps =
  | {
      icon?: IconFunctionComponent;
      children: string | RichStr;
      rightIcon?: IconFunctionComponent;
      responsiveHideText?: never;
    }
  | {
      icon: IconFunctionComponent;
      children?: string | RichStr;
      rightIcon?: IconFunctionComponent;
      responsiveHideText?: boolean;
    };

type ButtonProps = InteractiveStatelessProps &
  ButtonContentProps & {
    /**
     * Size preset — controls gap, text size, and Container height/rounding.
     */
    size?: ContainerSizeVariants;

    /** Tooltip text shown on hover. */
    tooltip?: string;

    /** Width preset. `"fit"` shrink-wraps, `"full"` stretches to parent width. */
    width?: ExtremaSizeVariants;

    /** Which side the tooltip appears on. */
    tooltipSide?: TooltipSide;

    /** Applies disabled styling and suppresses clicks. */
    disabled?: boolean;
  };

// ---------------------------------------------------------------------------
// Button
// ---------------------------------------------------------------------------

function ButtonIconSpacer({ size }: { size: ContainerSizeVariants }) {
  const { padding, size: iconSize } = iconVariants[size];

  return (
    <div aria-hidden="true" className={`${padding} invisible`}>
      <div
        className="shrink-0"
        style={{
          height: `${iconSize}rem`,
          width: `${iconSize}rem`,
        }}
      />
    </div>
  );
}

function Button({
  icon: Icon,
  children,
  rightIcon: RightIcon,
  size = "lg",
  type = "button",
  width,
  tooltip,
  tooltipSide = "top",
  responsiveHideText = false,
  disabled,
  ...interactiveProps
}: ButtonProps) {
  const isLarge = size === "lg";
  const shouldBalanceLeftIcon = Boolean(children && !Icon && RightIcon);
  const shouldBalanceRightIcon = Boolean(children && Icon && !RightIcon);

  const labelEl = children ? (
    responsiveHideText ? (
      <span className="hidden md:inline whitespace-nowrap">
        <Text
          font={isLarge ? "main-ui-body" : "secondary-body"}
          color="inherit"
        >
          {children}
        </Text>
      </span>
    ) : (
      <Text
        font={isLarge ? "main-ui-body" : "secondary-body"}
        color="inherit"
        nowrap
      >
        {children}
      </Text>
    )
  ) : null;
  const leftIconEl = Icon
    ? iconWrapper(Icon, size, false)
    : shouldBalanceLeftIcon
      ? <ButtonIconSpacer size={size} />
      : null;
  const rightIconEl = RightIcon
    ? iconWrapper(RightIcon, size, false)
    : shouldBalanceRightIcon
      ? <ButtonIconSpacer size={size} />
      : null;

  const button = (
    <Interactive.Stateless
      type={type}
      disabled={disabled}
      {...interactiveProps}
    >
      <Interactive.Container
        type={type}
        border={interactiveProps.prominence === "secondary"}
        size={size}
        width={width}
        rounding={isLarge ? "md" : size === "2xs" ? "xs" : "sm"}
      >
        <div className="flex flex-row items-center gap-1">
          {leftIconEl}

          {labelEl}
          {responsiveHideText ? (
            <span className="hidden md:inline-flex">
              {rightIconEl}
            </span>
          ) : (
            rightIconEl
          )}
        </div>
      </Interactive.Container>
    </Interactive.Stateless>
  );

  return (
    <Tooltip tooltip={tooltip} side={tooltipSide}>
      {button}
    </Tooltip>
  );
}

export { Button, type ButtonProps };
