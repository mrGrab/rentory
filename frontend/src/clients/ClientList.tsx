import {
  Datagrid,
  List,
  NumberField,
  TextField,
  FunctionField,
  SearchInput,
  TextInput,
} from "react-admin";

const clientFilters = [
  <SearchInput source="phone" alwaysOn key="phone" placeholder="Search by phone" />,
  <TextInput label="Name" source="given_name" />,
  <TextInput label="Surname" source="surname" />,
];

export const ClientList = () => (
  <List title="Clients" filters={clientFilters}>
    <Datagrid>
      <FunctionField
        label="Client"
        render={(record) =>
          record ? `${record.given_name} ${record.surname}` : ""
        }
      />
      <TextField source="phone" />
      <TextField source="instagram" />
      <TextField source="email" />
      <NumberField source="discount" />
      <FunctionField
        label="Orders"
        render={(record) => record.order_ids?.length ?? 0}
      />
      <TextField source="notes" />
    </Datagrid>
  </List>
);
