import { ResourceProps } from "react-admin";
import { OrderList } from "./OrderList.tsx";
import { OrderShow } from "./OrderShow";
import { OrderCreate } from "./OrderCreate";
import { OrderEdit } from "./OrderEdit";

const parseDateTime = (value: string) =>
  value ? new Date(value).toLocaleDateString() : value === "" ? null : value;

const orders: ResourceProps = {
  name: "orders",
  list: OrderList,
  show: OrderShow,
  create: OrderCreate,
  edit: OrderEdit,
  recordRepresentation: (order: any) => {
    return `${parseDateTime(order.start_time)} – ${parseDateTime(order.end_time)}`;
  },
};

export default orders;
