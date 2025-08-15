import { ResourceProps } from "react-admin";
import { ItemList } from "./ItemList";
import { ItemShow } from "./ItemShow";
import { ItemCreate } from "./ItemCreate";
import { ItemEdit } from "./ItemEdit";

const items: ResourceProps = {
  name: "items",
  list: ItemList,
  show: ItemShow,
  create: ItemCreate,
  edit: ItemEdit,
};

export default items;
