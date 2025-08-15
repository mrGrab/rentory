import { ResourceProps } from "react-admin";
import { ClientList } from "./ClientList";
import { ClientCreate } from "./ClientCreate";
import { ClientShow } from "./ClientShow";
import { ClientEdit } from "./ClientEdit";

const clients: ResourceProps = {
  name: "clients",
  list: ClientList,
  create: ClientCreate,
  show: ClientShow,
  edit: ClientEdit,
};
export default clients;
