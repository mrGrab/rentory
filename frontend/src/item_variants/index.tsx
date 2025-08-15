import { ResourceProps } from "react-admin";
import { VariantList } from "./List";

const variants: ResourceProps = {
  name: "variants",
  options: { label: "Maintenance" },
  list: VariantList,
};

export default variants;
