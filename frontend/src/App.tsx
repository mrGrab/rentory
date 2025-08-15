import { Admin, Resource, defaultTheme } from "react-admin";
import { Layout } from "./Layout";
import AssignmentIcon from "@mui/icons-material/Assignment";
import InventoryIcon from "@mui/icons-material/Inventory";
import PersonIcon from "@mui/icons-material/Person";
import DryCleaningIcon from "@mui/icons-material/DryCleaning";
import { LocalizationProvider } from "@mui/x-date-pickers";
import { AdapterDateFns } from "@mui/x-date-pickers/AdapterDateFns";
import { uk } from "date-fns/locale/uk";
import { deepmerge } from "@mui/utils";
import { authProvider } from "./authProvider";
import dataProvider from "./dataProvider";
import clients from "./clients";
import items from "./items";
import item_variants from "./item_variants";
import orders from "./orders";

const theme = deepmerge(defaultTheme, {
  sidebar: {
    width: 170, // The default value is 240
  },
});

export const App = () => (
  <LocalizationProvider dateAdapter={AdapterDateFns} adapterLocale={uk}>
    <Admin
      layout={Layout}
      authProvider={authProvider}
      dataProvider={dataProvider}
      disableTelemetry={true}
      theme={theme}
    >
      <Resource {...orders} icon={AssignmentIcon} />
      <Resource {...items} icon={InventoryIcon} />
      <Resource {...item_variants} icon={DryCleaningIcon} />
      <Resource {...clients} icon={PersonIcon} />
    </Admin>
  </LocalizationProvider>
);
