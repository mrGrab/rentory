import { useEffect, useState } from "react";
import { useFormContext, useWatch } from "react-hook-form";
import {
  Create,
  SimpleForm,
  TextInput,
  required,
  NumberInput,
  ReferenceInput,
  AutocompleteInput,
  useGetOne,
  email,
  maxLength,
  RaRecord,
  useCreateSuggestionContext,
  CreateBase,
  SaveButton,
  TextArrayInput,
} from "react-admin";
import { Box, Stack } from "@mui/material";
import Button from "@mui/material/Button";
import Dialog from "@mui/material/Dialog";
import DialogContent from "@mui/material/DialogContent";
import DialogTitle from "@mui/material/DialogTitle";
import PersonAddIcon from "@mui/icons-material/PersonAdd";
import PersonIcon from "@mui/icons-material/Person";
import DateRangeIcon from "@mui/icons-material/DateRange";
import { LocalizationProvider } from "@mui/x-date-pickers/LocalizationProvider";
import { AdapterDayjs } from "@mui/x-date-pickers/AdapterDayjs";
import { DatePicker } from "@mui/x-date-pickers/DatePicker";
import dayjs, { Dayjs } from "dayjs";
import { CardWrapper } from "../components/Card";
import {
  TotalPriceCalculator,
  EditItemsSection,
  EditDeliverySection,
  EditPaymentSection,
  EditNotesSection,
} from "./Common";

interface Client extends RaRecord {
  given_name?: string;
  surname?: string;
  phone: string;
  discount?: number;
}

// --- SECTIONS ---
const CreateClient = () => {
  const { filter, onCancel, onCreate } = useCreateSuggestionContext();
  const [initialPhone] = useState(filter || "");

  return (
    <Dialog open onClose={onCancel} fullWidth={true}>
      <DialogTitle
        sx={{
          m: 1,
          p: 1,
          display: "flex",
          alignItems: "center",
          gap: 1,
          color: "#1976d2",
        }}
      >
        <PersonAddIcon sx={{ fontSize: 30, color: "#1976d2" }} />
        Create New Client
      </DialogTitle>

      <DialogContent sx={{ p: 1 }}>
        <CreateBase
          redirect={false}
          resource="clients"
          record={{ phone: initialPhone }}
          mutationOptions={{
            onSuccess: onCreate,
          }}
        >
          <SimpleForm
            toolbar={
              <Box
                sx={{
                  display: "flex",
                  gap: 1,
                  justifyContent: "flex-end",
                  p: 1,
                }}
              >
                <Button
                  color="secondary"
                  variant="contained"
                  onClick={onCancel}
                  type="button"
                >
                  Cancel
                </Button>
                <SaveButton variant="contained" />
              </Box>
            }
          >
            <TextInput
              source="given_name"
              label="First Name"
              validate={required()}
            />
            <TextInput source="surname" label="Last Name" />
            <TextInput
              source="phone"
              label="Phone Number"
              validate={required()}
            />

            <TextInput
              source="email"
              label="Email Address"
              validate={[email(), maxLength(255)]}
            />

            <TextInput source="instagram" label="Instagram" />

            <NumberInput
              source="discount"
              label="Discount (%)"
              min="0"
              max="100"
            />

            <TextInput
              source="notes"
              label="Notes"
              multiline
              resettable
              rows={2}
              validate={maxLength(512)}
            />
          </SimpleForm>
        </CreateBase>
      </DialogContent>
    </Dialog>
  );
};

const ClientSelection = () => {
  const { setValue } = useFormContext();
  const clientId = useWatch({ name: "client_id" });

  const { data: client } = useGetOne<Client>(
    "clients",
    { id: clientId },
    { enabled: !!clientId },
  );

  useEffect(() => {
    if (client?.discount) {
      setValue("order_discount", client.discount);
    }
  }, [client, setValue]);

  return (
    <CardWrapper title="Client" icon={PersonIcon} sx={{ minWidth: 600 }}>
      <ReferenceInput
        reference="clients"
        source="client_id"
        label="Select Client"
      >
        <AutocompleteInput
          optionText={(client) =>
            `${client.phone} - ${client.surname || ""} ${client.given_name || ""}`.trim()
          }
          filterToQuery={(searchText) => ({ phone: searchText })}
          create={<CreateClient />}
          createLabel="Start typing to create a new Client"
          createItemLabel="Add a new client: %{item}"
          suggestionLimit={3}
          debounce={500}
          disablePortal
          validate={required()}
        />
      </ReferenceInput>
    </CardWrapper>
  );
};

export const DateSection = () => {
  const { control, setValue } = useFormContext();

  const startTime: string = useWatch({ control, name: "start_time" }) || "";
  const endTime: string = useWatch({ control, name: "end_time" }) || "";

  const handleStartChange = (value: Dayjs | Date | null) => {
    const dayjsValue = value ? dayjs(value) : null;
    setValue("start_time", dayjsValue ? dayjsValue.format("YYYY-MM-DD") : "", {
      shouldValidate: true,
    });
    if (endTime && dayjsValue && dayjs(endTime).isBefore(dayjsValue, "day")) {
      setValue("end_time", "", { shouldValidate: true });
    }
  };

  const handleEndChange = (value: Dayjs | Date | null) => {
    const dayjsValue = value ? dayjs(value) : null;
    setValue("end_time", dayjsValue ? dayjsValue.format("YYYY-MM-DD") : "", {
      shouldValidate: true,
    });
  };

  return (
    <CardWrapper
      title="Rental Period"
      icon={DateRangeIcon}
      sx={{ minWidth: 600 }}
    >
      <LocalizationProvider dateAdapter={AdapterDayjs} adapterLocale="uk">
        <Box display="flex" gap={2}>
          <DatePicker
            label="Start"
            value={startTime ? dayjs(startTime, "YYYY-MM-DD") : null}
            onChange={handleStartChange}
            format="D MMM YYYY"
            slotProps={{ textField: { variant: "filled", size: "small" } }}
          />
          <DatePicker
            label="End"
            value={endTime ? dayjs(endTime, "YYYY-MM-DD") : null}
            onChange={handleEndChange}
            minDate={startTime ? dayjs(startTime, "YYYY-MM-DD") : undefined}
            format="D MMM YYYY"
            slotProps={{ textField: { variant: "filled", size: "small" } }}
          />
        </Box>
      </LocalizationProvider>
    </CardWrapper>
  );
};

// --- MAIN CREATE VIEW ---
export const OrderCreate = () => (
  <Create redirect="show" title="Create New Order">
    <SimpleForm>
      <TotalPriceCalculator />
      <Stack spacing={3}>
        <ClientSelection />
        <DateSection />
        <EditItemsSection />
        <EditDeliverySection />
        <EditPaymentSection />
        <EditNotesSection />
        <TextArrayInput source="tags" label="Tags" />
      </Stack>
    </SimpleForm>
  </Create>
);
