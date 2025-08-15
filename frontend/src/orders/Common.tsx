import { useEffect, useState } from "react";
import { useFormContext, useWatch, FieldValues } from "react-hook-form";
import {
  ReferenceField,
  FunctionField,
  Identifier,
  NumberInput,
  RaRecord,
  useDataProvider,
  SelectInput,
  AutocompleteInput,
  ReferenceInput,
  FormDataConsumer,
  SimpleFormIterator,
  ArrayInput,
  TextInput,
} from "react-admin";
import { Typography, Box } from "@mui/material";
import PersonIcon from "@mui/icons-material/Person";
import InventoryIcon from "@mui/icons-material/Inventory";
import LocalShippingIcon from "@mui/icons-material/LocalShipping";
import MonetizationOnIcon from "@mui/icons-material/MonetizationOn";
import NotesIcon from "@mui/icons-material/Notes";
import { CardWrapper } from "../components/Card";

export interface FormItem {
  item_id: Identifier;
  item_variant_id: Identifier;
  price?: number;
  quantity?: number;
}

interface Price {
  amount: number;
  price_type: string;
}
interface Variant {
  id: string;
  size?: string;
  color?: string;
  status: string;
  stock_quantity: number;
  prices: Price[];
  available: boolean;
}

interface Item extends RaRecord {
  title: string;
  variants: Variant[];
}

export const LabelValue = ({
  label,
  children,
}: {
  label: React.ReactNode;
  children: React.ReactNode;
}) => (
  <Box display="flex" gap={1} alignItems="center" sx={{ whiteSpace: "normal" }}>
    <Typography fontWeight={500} whiteSpace="nowrap">
      {label}
    </Typography>
    {children}
  </Box>
);

export const ShowClientInfo = ({
  clientIdField = "client_id",
}: {
  clientIdField?: string;
}) => (
  <ReferenceField
    source={clientIdField}
    reference="clients"
    link={false}
    label={false}
  >
    <FunctionField
      label={false}
      render={(client) => (
        <CardWrapper
          title={`${client?.given_name ?? ""}${client?.surname ? " " + client.surname : ""}`}
          icon={PersonIcon}
        >
          <Box display="flex" flexDirection="column" gap={1}>
            <LabelValue label="Phone:">
              <Typography>{client?.phone ?? "—"}</Typography>
            </LabelValue>
            {client?.email && (
              <LabelValue label="Email:">
                <Typography>{client.email}</Typography>
              </LabelValue>
            )}
            {client?.instagram && (
              <LabelValue label="Instagram:">
                <Typography>{client.instagram}</Typography>
              </LabelValue>
            )}
          </Box>
        </CardWrapper>
      )}
    />
  </ReferenceField>
);

/* This component calculates the total but renders nothing */
export const TotalPriceCalculator = () => {
  const { setValue } = useFormContext();

  const items = useWatch({ name: "items" });
  const discount = useWatch({ name: "order_discount" });
  const deliveryCost = useWatch({ name: "delivery_info.cost" });

  useEffect(() => {
    const subtotal = (items || []).reduce(
      (acc: number, currentItem: FormItem) => {
        const price = Number(currentItem.price) || 0;
        return acc + price;
      },
      0,
    );

    const discountedSubtotal =
      subtotal - (subtotal * (Number(discount) || 0)) / 100;
    const finalTotal = discountedSubtotal + (Number(deliveryCost) || 0);

    setValue("payment_details.total", finalTotal, { shouldValidate: true });
  }, [items, discount, deliveryCost, setValue]);

  return null;
};

const ItemRow = ({ scopedFormData }: { scopedFormData?: FieldValues }) => {
  const dataProvider = useDataProvider();
  const { getValues } = useFormContext();
  const [item, setItem] = useState<Item | undefined>();

  const itemId = scopedFormData?.item_id;

  useEffect(() => {
    const fetchItem = async () => {
      const { start_time, end_time } = getValues();
      const from = start_time ? new Date(start_time).toISOString() : undefined;
      const to = end_time ? new Date(end_time).toISOString() : undefined;

      if (itemId && from && to) {
        const result = await dataProvider.getItemWithAvailability(itemId, {
          start_time: from,
          end_time: to,
        });
        setItem(result);
      } else {
        setItem(undefined);
      }
    };

    fetchItem();
  }, [itemId, getValues, dataProvider]);

  const selectedVariant = item?.variants?.find(
    (v) => v.id === scopedFormData?.item_variant_id,
  );

  const formatVariantName = (variant: Variant) => {
    const size = `${variant.size || ""}`;
    const color = `${variant.color || ""}`;
    const stock =
      variant.stock_quantity > 1 ? `(Stock: ${variant.stock_quantity})` : "";
    const status = variant.status === "available" ? "" : " - Unavailable";
    return `${size} ${color} ${stock}${status}`.trim();
  };

  const variantChoices =
    item?.variants?.map((variant) => ({
      id: variant.id,
      name: formatVariantName(variant),
      disabled: variant.status != "available",
    })) ?? [];

  const priceChoices =
    selectedVariant?.prices?.map((p) => ({
      id: p.amount,
      name: `${p.price_type}: ${p.amount}`,
    })) || [];

  return (
    <Box display="flex" gap={2} alignItems="flex-start">
      <Box sx={{ flex: 1 }}>
        <ReferenceInput reference="items" source="item_id" label="Item">
          <AutocompleteInput optionText="title" label="Item" fullWidth />
        </ReferenceInput>
      </Box>

      <Box sx={{ flex: 1 }}>
        <SelectInput
          source="item_variant_id"
          label="Variant"
          choices={variantChoices}
          disabled={!item || variantChoices.length === 0}
          fullWidth
        />
      </Box>

      {selectedVariant && (
        <Box flex={1}>
          {priceChoices.length > 0 ? (
            <SelectInput
              source="price"
              label="Price"
              choices={priceChoices}
              fullWidth
            />
          ) : (
            <NumberInput
              source="price"
              label="Custom Price"
              min={0}
              fullWidth
            />
          )}
        </Box>
      )}
    </Box>
  );
};

export const EditItemsSection = () => (
  <CardWrapper title="Items" icon={InventoryIcon} sx={{ minWidth: 600 }}>
    <ArrayInput source="items" label={false}>
      <SimpleFormIterator disableReordering inline>
        <FormDataConsumer>
          {({ scopedFormData }) => <ItemRow scopedFormData={scopedFormData} />}
        </FormDataConsumer>{" "}
      </SimpleFormIterator>
    </ArrayInput>
  </CardWrapper>
);

export const EditDeliverySection = () => (
  <CardWrapper title="Delivery" icon={LocalShippingIcon} sx={{ minWidth: 600 }}>
    <SelectInput
      source="delivery_info.pickup_type"
      label="Pickup Type"
      choices={[
        { id: "showroom", name: "Showroom" },
        { id: "taxi", name: "Taxi" },
        { id: "postal_service", name: "Postal Service" },
      ]}
    />

    <TextInput source="delivery_info.address" label="Delivery Address" />
  </CardWrapper>
);

export const EditPaymentSection = () => (
  <CardWrapper
    title="Payment Details"
    icon={MonetizationOnIcon}
    sx={{ minWidth: 600 }}
  >
    <Box display="flex" flexDirection="column" gap={1} width="100%">
      <Box display="flex" alignItems="center" gap={2}>
        <Box flex={1}>
          <NumberInput
            source="order_discount"
            label="Discount (%)"
            min={0}
            defaultValue={0}
            max={100}
          />
        </Box>
        <Box flex={1}>
          <NumberInput
            source="payment_details.total"
            label="Total Amount"
            readOnly
          />
        </Box>
      </Box>
      <Box display="flex" alignItems="center" gap={2}>
        <Box flex={1}>
          <NumberInput
            source="payment_details.deposit"
            label="Deposit"
            min={0}
          />
        </Box>
        <Box flex={1}>
          <NumberInput source="payment_details.paid" label="Paid" min={0} />
        </Box>
        <Box flex={1}>
          <SelectInput
            source="payment_details.payment_type"
            label="Type"
            choices={[
              { id: "cash", name: "Cash" },
              { id: "card", name: "Card" },
              { id: "deposit", name: "Deposit" },
              { id: "bank_transfer", name: "Bank Transfer" },
            ]}
          />
        </Box>
      </Box>
    </Box>
  </CardWrapper>
);

export const EditNotesSection = () => (
  <CardWrapper title="Other Details" icon={NotesIcon} sx={{ minWidth: 600 }}>
    <TextInput
      source="notes"
      multiline
      resettable
      rows={3}
      fullWidth
      label={false}
    />
  </CardWrapper>
);
