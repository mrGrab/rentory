import {
  Datagrid,
  DateField,
  List,
  TextField,
  FunctionField,
  TextInput,
  ReferenceField,
  SelectInput,
  ReferenceArrayInput,
  AutocompleteArrayInput,
  DateInput,
  SearchInput,
} from "react-admin";
import {
  ItemsListChip,
  TagsList,
  ORDER_STATUS,
  OrderStatusChip,
} from "../components/Common";

const orderFilters = [
  <SearchInput source="id" key="id" placeholder="Search by ID" alwaysOn />,
  <DateInput label="Rent start" source="start_time" />,
  <DateInput label="Rent end" source="end_time" />,
  <TextInput key="phone" label="Client phone" source="phone" />,
  <SelectInput
    key="status"
    label="Status"
    source="status"
    choices={Object.entries(ORDER_STATUS).map(([key, { label }]) => ({
      id: key,
      name: label,
    }))}
  />,
  <ReferenceArrayInput
    key="items"
    source="item_ids"
    reference="items"
    label="Items"
  >
    <AutocompleteArrayInput optionText="title" />
  </ReferenceArrayInput>,
  <TextInput label="Tag" source="tag" />,
  <SelectInput
    key="pickup_type"
    label="Pickup"
    source="pickup_type"
    choices={[
      { id: "showroom", name: "Showroom" },
      { id: "taxi", name: "Taxi" },
      { id: "postal_service", name: "Postal Service" },
    ]}
  />,
];

export const OrderList = () => (
  <List title="Orders" resource="orders" filters={orderFilters}>
    <Datagrid>
      <TextField source="id" label="ID" />
      <ReferenceField source="client_id" reference="clients" label="Client">
        <FunctionField
          render={(client: any) =>
            `${client.surname || ""} ${client.given_name || ""}`.trim()
          }
        />
      </ReferenceField>
      <ReferenceField
        source="client_id"
        reference="clients"
        label="Phone"
        link={false}
      >
        <TextField source="phone" />
      </ReferenceField>
      <DateField
        source="start_time"
        label="Start"
        locales="en-GB"
        options={{ year: "numeric", month: "short", day: "numeric" }}
      />
      <DateField
        source="end_time"
        label="End"
        locales="en-GB"
        options={{ year: "numeric", month: "short", day: "numeric" }}
      />
      <FunctionField label="Items" render={() => <ItemsListChip />} />

      <TextField source="delivery_info.pickup_type" label="Pickup" />

      <TextField source="notes" />

      <FunctionField label="Tags" render={() => <TagsList />} />

      <FunctionField
        label="Status"
        render={() => <OrderStatusChip />}
        sortBy="status"
      />
    </Datagrid>
  </List>
);
