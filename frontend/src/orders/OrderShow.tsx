import {
  Show,
  SimpleShowLayout,
  TextField,
  ReferenceField,
  FunctionField,
  ArrayField,
  Datagrid,
} from "react-admin";
import { Typography, Box } from "@mui/material";
import { CardWrapper } from "../components/Card";
import InventoryIcon from "@mui/icons-material/Inventory";
import NotesIcon from "@mui/icons-material/Notes";
import AssignmentIcon from "@mui/icons-material/Assignment";
import PaymentIcon from "@mui/icons-material/Payment";
import LocalShippingIcon from "@mui/icons-material/LocalShipping";
import {
  TagsList,
  OrderStatusChip,
  ShowActions,
  ShowDateField,
} from "../components/Common";
import { LabelValue, ShowClientInfo, FormItem } from "./Common";

const PaymentDetails = ({ record }: { record: any }) => {
  const payment = record.payment_details || {};
  const discountPercent = record.order_discount || 0;
  const items = record.items || [];

  const itemsCost = items.reduce((sum: number, item: FormItem) => {
    const price = item.price || 0;
    const quantity = item.quantity || 1;
    return sum + price * quantity;
  }, 0);

  const discountValue = Math.round((itemsCost * discountPercent) / 100);
  const discountedItemsCost = itemsCost - discountValue;
  const paid = payment.paid || 0;
  const amountDue = discountedItemsCost - paid;
  const to_pay = amountDue + payment.deposit;

  return (
    <Box display="flex" flexDirection="column" gap={1}>
      <LabelValue label="Items Total:">
        <Typography>{itemsCost}</Typography>
      </LabelValue>

      {discountPercent > 0 && (
        <LabelValue label={`Discount (${discountPercent}%):`}>
          <Typography>-{discountValue}</Typography>
        </LabelValue>
      )}

      <LabelValue label="Total:">
        <Typography fontWeight={600}>{discountedItemsCost}</Typography>
      </LabelValue>

      <Box sx={{ borderTop: 1, borderColor: "divider", pt: 1, mt: 1 }}>
        <LabelValue label="Payment Type:">
          <Typography>{payment.payment_type || "—"}</Typography>
        </LabelValue>

        <LabelValue label="Paid:">
          <Typography>{paid}</Typography>
        </LabelValue>

        {payment.transaction_id && (
          <LabelValue label="Transaction ID:">
            <Typography>{payment.transaction_id}</Typography>
          </LabelValue>
        )}
        <LabelValue label="Deposit:">
          <Typography>{payment.deposit}</Typography>
        </LabelValue>
      </Box>

      <Box sx={{ borderTop: 1, borderColor: "divider", pt: 1, mt: 1 }}>
        <LabelValue label="Amount Due:">
          <Typography
            color={amountDue > 0 ? "error" : "success.main"}
            fontWeight={600}
          >
            {amountDue > 0 ? amountDue : "0"}
          </Typography>
        </LabelValue>
        <LabelValue label="To pay:">
          <Typography>{to_pay}</Typography>
        </LabelValue>
      </Box>
    </Box>
  );
};

// --- MAIN SHOW VIEW ---
export const OrderShow = () => (
  <Show actions={<ShowActions />} title="Order Details">
    <SimpleShowLayout>
      {/* Order Info */}
      <FunctionField
        label={false}
        render={(order) => (
          <CardWrapper
            title={`Order #${order.id}`}
            icon={AssignmentIcon}
            sx={{ width: "100%", minWidth: 600 }}
          >
            <LabelValue label="Status:">
              <OrderStatusChip />
            </LabelValue>

            <LabelValue label="Pickup:">
              <TextField source="delivery_info.pickup_type" record={order} />
            </LabelValue>

            <LabelValue label="Start:">
              <ShowDateField source="start_time" label="start_time" />
            </LabelValue>

            <LabelValue label="End:">
              <ShowDateField source="end_time" label="end_time" />
            </LabelValue>

            <LabelValue label="Tags:">
              <TagsList />
            </LabelValue>
          </CardWrapper>
        )}
      />

      {/* Client Info */}
      <FunctionField label={false} render={() => <ShowClientInfo />} />

      {/* Delivery Information */}
      <CardWrapper title="Delivery Information" icon={LocalShippingIcon}>
        <Box display="flex" flexDirection="column" gap={1}>
          <LabelValue label="Method:">
            <TextField source="delivery_info.pickup_type"></TextField>
          </LabelValue>
          <LabelValue label="Address:">
            <TextField source="delivery_info.address"></TextField>
          </LabelValue>
          <LabelValue label="Tracking:">
            <TextField source="delivery_info.tracking_number"></TextField>
          </LabelValue>
        </Box>
      </CardWrapper>

      {/* Items */}
      <CardWrapper title="Items" icon={InventoryIcon}>
        <ArrayField source="items">
          <Datagrid
            optimized
            size="small"
            bulkActionButtons={false}
            rowClick={false}
          >
            <ReferenceField source="item_id" reference="items">
              <TextField source="title" />
            </ReferenceField>
            <FunctionField
              label="Size"
              render={(variant: any) => variant.size ?? "—"}
            />
            <FunctionField
              label="Color"
              render={(variant: any) => variant.color ?? "—"}
            />
            <FunctionField
              label="Quantity"
              render={(variant: any) => variant.quantity ?? "1"}
            />
            <FunctionField
              label="Price"
              render={(variant: any) => `${variant.price ?? 0}`}
            />
          </Datagrid>
        </ArrayField>
      </CardWrapper>

      {/* Payment Details */}
      <CardWrapper title="Payment Details" icon={PaymentIcon}>
        <FunctionField
          label={false}
          render={(record) => <PaymentDetails record={record} />}
        />
      </CardWrapper>

      {/* Notes */}
      <CardWrapper title="Notes" icon={NotesIcon}>
        <TextField source="notes" />
      </CardWrapper>
    </SimpleShowLayout>
  </Show>
);
