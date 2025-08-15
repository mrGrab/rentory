import {
  Datagrid,
  List,
  FunctionField,
  TextField,
  SearchInput,
  useDataProvider,
  SelectInput,
  SelectInputProps,
  TextInput,
} from "react-admin";
import { useEffect, useState } from "react";
import { Box, Stack, Chip, Avatar } from "@mui/material";
import { ItemStatusChip, TagsList } from "../components/Common";

// Type definitions
interface Variant {
  size?: string;
  color?: string;
  stock_quantity: number;
}

interface ItemRecord {
  id: string;
  title: string;
  image_url?: string;
  category?: string;
  variants?: Variant[];
  tags?: string[];
  description?: string;
  order_ids?: string[];
  status: "in_stock" | "out_of_stock";
}

// item title with image
const ItemTitle = ({ record }: { record: ItemRecord }) => {
  return (
    <Box display="flex" alignItems="center" gap={1.5}>
      {record.image_url ? (
        <Avatar
          src={record.image_url}
          alt={record.title}
          variant="rounded"
          sx={{ width: 40, height: 40 }}
        />
      ) : (
        <Box width={40} height={40} />
      )}
      <span>{record.title}</span>
    </Box>
  );
};

// item variant chips
const VariantChips = ({ record }: { record: ItemRecord | null }) => {
  if (!record) return null;

  const variants =
    record.variants?.filter((v) => v.stock_quantity != null) || [];

  return (
    <Stack direction="row" flexWrap="wrap" gap={0.5}>
      {variants.map((variant, idx) => {
        const parts = [variant.size, variant.color].filter(Boolean);
        const label = parts.length
          ? `${parts.join(" ")}${variant.stock_quantity > 1 ? ` (${variant.stock_quantity})` : ""}`
          : `${variant.stock_quantity}`;

        return <Chip key={idx} label={label} variant="filled" />;
      })}
    </Stack>
  );
};

// Filter configuration
const DistinctValueFilterInput = ({
  fetchValues,
  ...props
}: SelectInputProps & {
  fetchValues: (dataProvider: any) => Promise<string[]>;
}) => {
  const [choices, setChoices] = useState<{ id: string; name: string }[]>([]);
  const dataProvider = useDataProvider();

  useEffect(() => {
    fetchValues(dataProvider).then((values) => {
      setChoices(values.map((val) => ({ id: val, name: val })));
    });
  }, [dataProvider, fetchValues]);

  return <SelectInput {...props} choices={choices} emptyText="All" />;
};

const itemFilters = [
  <SearchInput
    source="title"
    key="title"
    placeholder="Search by title"
    alwaysOn
  />,
  <DistinctValueFilterInput
    source="category"
    label="Category"
    key="filter-category"
    fetchValues={(dataProvider) => dataProvider.getItemCategories()}
  />,
  <DistinctValueFilterInput
    source="size"
    label="Size"
    key="filter-size"
    fetchValues={(dataProvider) => dataProvider.getItemSizes()}
  />,
  <DistinctValueFilterInput
    source="color"
    label="Color"
    key="filter-color"
    fetchValues={(dataProvider) => dataProvider.getItemColors()}
  />,
  <DistinctValueFilterInput
    source="status"
    label="Status"
    key="filter-status"
    fetchValues={(dataProvider) => dataProvider.getItemStatuses()}
  />,
  <DistinctValueFilterInput
    source="variant_status"
    label="Variant status"
    key="filter-variant-status"
    fetchValues={(dataProvider) => dataProvider.getItemVariantStatuses()}
  />,
  <TextInput label="Tag" source="tag" />,
];

export const ItemList = () => (
  <List title="Available Items" filters={itemFilters}>
    <Datagrid>
      <FunctionField
        label="Title"
        render={(record) => <ItemTitle record={record as ItemRecord} />}
        sortBy="title"
      />
      <TextField source="category" />
      <FunctionField
        label="Variants"
        render={(record) => <VariantChips record={record} />}
      />
      <TextField source="description" sortable={false} />
      <FunctionField label="Tags" render={() => <TagsList />} />
      <FunctionField
        label="Status"
        render={() => <ItemStatusChip />}
        sortBy="status"
      />
    </Datagrid>
  </List>
);
