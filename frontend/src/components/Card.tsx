import {
  Card as MuiCard,
  CardContent,
  CardHeader,
  SxProps,
  Theme,
} from "@mui/material";
import type { SvgIconProps } from "@mui/material";
import type { ReactNode } from "react";

export interface CardProps {
  children: ReactNode;
  title?: string;
  icon?: React.ElementType<SvgIconProps>;
  sx?: SxProps<Theme>;
}

export const CardWrapper = ({ children, title, icon: Icon, sx }: CardProps) => (
  <MuiCard sx={{ mb: 3, boxShadow: 2, borderRadius: 4, ...sx }}>
    {title && (
      <CardHeader
        title={title}
        avatar={Icon ? <Icon sx={{ fontSize: 30, color: "#1976d2" }} /> : ""}
        slotProps={{
          title: {
            sx: {
              color: "#1976d2",
              fontWeight: "bold",
              fontSize: "h6.fontSize",
            },
          },
        }}
      />
    )}
    <CardContent>{children}</CardContent>
  </MuiCard>
);
