import {
  Show,
  SimpleShowLayout,
  TextField,
  Datagrid,
  FunctionField,
  useRecordContext,
  ArrayField,
  ReferenceArrayField,
} from "react-admin";
import { Typography, Avatar, Box, Grid } from "@mui/material";
import InventoryIcon from "@mui/icons-material/Inventory";
import { CardWrapper } from "../components/Card";
import {
  ItemStatusChip,
  VariantStatusChip,
  TagsList,
  ShowOrderHistory,
  ShowActions,
} from "../components/Common";

const ItemHeader = () => {
  const record = useRecordContext();
  if (!record) return null;

  return (
    <Grid container spacing={2} alignItems="center" sx={{ mb: 3 }}>
      <Grid>
        <Avatar
          src={record.image_url}
          alt={record.title}
          variant="rounded"
          sx={{ width: 100, height: 100 }}
        />
      </Grid>
      <Grid>
        <Typography variant="h4" gutterBottom>
          {record.title}
        </Typography>
        <Typography variant="subtitle1" color="textSecondary" gutterBottom>
          {record.category}
        </Typography>
        <Box display="flex" gap={1} flexWrap="wrap">
          <ItemStatusChip />
          <TagsList />
        </Box>
      </Grid>
    </Grid>
  );
};

const VariantsList = () => {
  const record = useRecordContext();
  const variants = record?.variants || [];

  if (!variants.length) {
    return <Typography color="text.secondary">No variants</Typography>;
  }

  return (
    <ArrayField source="variants">
      <Datagrid bulkActionButtons={false} rowClick={false}>
        <TextField source="size" />
        <TextField source="color" />
        <TextField source="stock_quantity" label="Stock" />
        <FunctionField
          label="Prices"
          render={(variant: any) =>
            (variant.prices || [])
              .map((price: any) => `${price.price_type}: ${price.amount}`)
              .join(", ") || "N/A"
          }
        />

        <FunctionField
          label="Status"
          render={() => <VariantStatusChip />}
          sortBy="status"
        />
      </Datagrid>
    </ArrayField>
  );
};

export const ItemShow = () => (
  <Show actions={<ShowActions />}>
    <SimpleShowLayout>
      <CardWrapper>
        <FunctionField render={() => <ItemHeader />} />
        <TextField source="description" />
      </CardWrapper>

      <CardWrapper title="Product Variants" icon={InventoryIcon}>
        <FunctionField render={() => <VariantsList />} />
      </CardWrapper>

      <CardWrapper title="Order History" icon={InventoryIcon}>
        <ReferenceArrayField reference="orders" source="order_ids">
          <ShowOrderHistory />
        </ReferenceArrayField>
      </CardWrapper>
    </SimpleShowLayout>
  </Show>
);
