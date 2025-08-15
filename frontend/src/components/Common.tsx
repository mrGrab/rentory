import {
  FunctionField,
  useRecordContext,
  SingleFieldList,
  ReferenceArrayField,
  TopToolbar,
  EditButton,
  DateField,
  Datagrid,
  TextField,
  ReferenceField,
} from "react-admin";
import { Chip } from "@mui/material";

const STATUS_COLOR_CONFIG = {
  success: { color: "#2e7d32", bg: "#e8f5e9" },
  error: { color: "#c62828", bg: "#ffebee" },
  warning: { color: "#f9a825", bg: "#fff8e1" },
  info: { color: "#1565c0", bg: "#e3f2fd" },
  neutral: { color: "#424242", bg: "#f5f5f5" },
  default: { color: "#666", bg: "#eee" },
};

export const VARIANT_STATUS = {
  available: { ...STATUS_COLOR_CONFIG.success, label: "AVAILABLE" },
  repair: { ...STATUS_COLOR_CONFIG.error, label: "REPAIR" },
  cleaning: { ...STATUS_COLOR_CONFIG.warning, label: "CLEANING" },
  unavailable: { ...STATUS_COLOR_CONFIG.neutral, label: "UNAVAILABLE" },
};

export const ITEM_STATUS = {
  in_stock: { ...STATUS_COLOR_CONFIG.success, label: "IN STOCK" },
  out_of_stock: { ...STATUS_COLOR_CONFIG.error, label: "OUT OF STOCK" },
};

export const ORDER_STATUS = {
  booked: { ...STATUS_COLOR_CONFIG.success, label: "BOOKED" },
  issued: { ...STATUS_COLOR_CONFIG.info, label: "ISSUED" },
  returned: { ...STATUS_COLOR_CONFIG.info, label: "RETURNED" },
  canceled: { ...STATUS_COLOR_CONFIG.warning, label: "CANCELED" },
  done: { ...STATUS_COLOR_CONFIG.neutral, label: "DONE" },
};

const StatusChip = ({
  statusKey,
  config,
}: {
  statusKey: string | undefined;
  config: Record<string, { color: string; bg: string; label: string }>;
}) => {
  if (!statusKey) return null;

  const status = config[statusKey] || {
    ...STATUS_COLOR_CONFIG.default,
    label: statusKey.toUpperCase(),
  };

  return (
    <Chip
      label={status.label}
      size="small"
      style={{
        color: status.color,
        backgroundColor: status.bg,
        fontWeight: 500,
      }}
    />
  );
};

export const OrderStatusChip = () => {
  const record = useRecordContext();
  return <StatusChip statusKey={record?.status} config={ORDER_STATUS} />;
};

export const VariantStatusChip = () => {
  const record = useRecordContext();
  return <StatusChip statusKey={record?.status} config={VARIANT_STATUS} />;
};

export const ItemStatusChip = () => {
  const record = useRecordContext();
  return <StatusChip statusKey={record?.status} config={ITEM_STATUS} />;
};

export const ItemsListChip = () => {
  const record = useRecordContext();
  const itemIds = record?.items?.map((item: any) => item.item_id) || [];

  if (!itemIds.length || !record?.id) return <span>No items</span>;

  return (
    <ReferenceArrayField
      reference="items"
      source="item_ids"
      record={{ id: record.id, item_ids: itemIds }}
    >
      <SingleFieldList linkType="show">
        <FunctionField
          render={(item: any) => (
            <Chip
              label={`${item.title} ${item.category || ""}`.trim()}
              clickable
              size="small"
              color="info"
            />
          )}
        />
      </SingleFieldList>
    </ReferenceArrayField>
  );
};

export const TagsList = () => {
  const record = useRecordContext();
  const tags = record?.tags || [];

  if (!tags.length) return null;

  return (
    <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
      {tags.map((tag: string, index: number) => (
        <Chip key={index} label={tag} size="small" variant="outlined" />
      ))}
    </div>
  );
};

export const ShowActions = () => (
  <TopToolbar>
    <EditButton />
  </TopToolbar>
);

export const ShowDateField = (props: { source: string; label: string }) => (
  <DateField
    {...props}
    locales="en-GB"
    options={{ year: "numeric", month: "short", day: "numeric" }}
  />
);

export const ShowOrderHistory = () => (
  <Datagrid optimized size="small" bulkActionButtons={false} rowClick={false}>
    <ReferenceField source="id" reference="orders" label="ID" link="show">
      <TextField source="id" />
    </ReferenceField>
    <FunctionField label="Items" render={() => <ItemsListChip />} />
    <ShowDateField source="start_time" label="Start" />
    <ShowDateField source="end_time" label="End" />
    <TextField source="order_discount" label="Discount" />
    <TextField source="delivery_info.pickup_type" label="Pickup" />
    <FunctionField
      label="Total"
      render={(record: any) => record?.payment_details?.total ?? "0"}
    />
    <FunctionField
      label="Deposit"
      render={(record: any) => record?.payment_details?.deposit ?? "—"}
    />
    <FunctionField
      label="Status"
      render={() => <OrderStatusChip />}
      sortBy="status"
    />
  </Datagrid>
);
