import {
  Edit,
  SimpleForm,
  DateInput,
  SelectInput,
  useRecordContext,
  TextArrayInput,
} from "react-admin";
import { Stack } from "@mui/material";
import AssignmentIcon from "@mui/icons-material/Assignment";
import { CardWrapper } from "../components/Card";
import { ORDER_STATUS } from "../components/Common";
import {
  ShowClientInfo,
  TotalPriceCalculator,
  LabelValue,
  EditItemsSection,
  EditDeliverySection,
  EditPaymentSection,
  EditNotesSection,
} from "./Common";

const OrderInfoSection = () => {
  const record = useRecordContext();

  return (
    <CardWrapper title={`Order #${record?.id}`} icon={AssignmentIcon}>
      <LabelValue label="Status:">
        <SelectInput
          source="status"
          choices={Object.entries(ORDER_STATUS).map(([key, { label }]) => ({
            id: key,
            name: label,
          }))}
          sx={{ width: 185 }}
        />
      </LabelValue>

      <LabelValue label="Dates:">
        <DateInput source="start_time" label="Start" sx={{ width: 190 }} />
        <DateInput source="end_time" label="End" sx={{ width: 190 }} />
      </LabelValue>

      <LabelValue label="Tags:">
        <TextArrayInput
          source="tags"
          label={false}
          helperText="Press Enter after each tag"
          sx={{ width: 395 }}
        />
      </LabelValue>
    </CardWrapper>
  );
};

// --- Main Edit View ---
export const OrderEdit = () => (
  <Edit title="Edit Order" redirect="show">
    <SimpleForm>
      <TotalPriceCalculator />
      <Stack spacing={3}>
        <OrderInfoSection />
        <ShowClientInfo />
        <EditItemsSection />
        <EditDeliverySection />
        <EditPaymentSection />
        <EditNotesSection />
      </Stack>
    </SimpleForm>
  </Edit>
);
