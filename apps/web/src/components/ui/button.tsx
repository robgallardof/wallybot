import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import { clsx } from "clsx";
import { twMerge } from "tailwind-merge";

const styles = cva("button", {
  variants: {
    variant: { default: "button-primary", outline: "button-outline" },
  },
  defaultVariants: { variant: "default" },
});
type Props = React.ButtonHTMLAttributes<HTMLButtonElement> &
  VariantProps<typeof styles> & { asChild?: boolean };
export function Button({
  className,
  variant,
  asChild = false,
  ...props
}: Props) {
  const Comp = asChild ? Slot : "button";
  return (
    <Comp
      className={twMerge(clsx(styles({ variant }), className))}
      {...props}
    />
  );
}
