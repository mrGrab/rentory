import {
  Show,
  SimpleShowLayout,
  TextField,
  ReferenceManyField,
} from "react-admin";
import PersonIcon from "@mui/icons-material/Person";
import InventoryIcon from "@mui/icons-material/Inventory";
import PhoneIcon from "@mui/icons-material/Phone";
import EmailIcon from "@mui/icons-material/Email";
import InstagramIcon from "@mui/icons-material/Instagram";
import LocalOfferIcon from "@mui/icons-material/LocalOffer";
import NotesIcon from "@mui/icons-material/Notes";
import { CardWrapper } from "../components/Card";
import { ShowOrderHistory, ShowActions } from "../components/Common";

type FieldGroupProps = {
  label: string;
  children: any;
  icon?: any;
};

const FieldGroup = ({ label, children, icon: Icon }: FieldGroupProps) => (
  <div style={{ marginBottom: "16px" }}>
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: "8px",
        marginBottom: "4px",
      }}
    >
      {Icon && <Icon sx={{ fontSize: 16, color: "#757575" }} />}
      <span
        style={{
          fontSize: "12px",
          color: "#757575",
          fontWeight: 500,
          textTransform: "uppercase",
        }}
      >
        {label}
      </span>
    </div>
    <div style={{ marginLeft: Icon ? "24px" : "0" }}>{children}</div>
  </div>
);

export const ClientShow = () => (
  <Show actions={<ShowActions />} title="Client Details">
    <SimpleShowLayout>
      <CardWrapper title="Information" icon={PersonIcon}>
        <FieldGroup label="Full Name" icon={PersonIcon}>
          <div style={{ display: "flex", gap: "4px" }}>
            <TextField source="given_name" />
            <TextField source="surname" />
          </div>
        </FieldGroup>

        <FieldGroup label="Contact" icon={PhoneIcon}>
          <TextField source="phone" />
        </FieldGroup>

        <FieldGroup label="Email" icon={EmailIcon}>
          <TextField source="email" />
        </FieldGroup>

        <FieldGroup label="Social Media" icon={InstagramIcon}>
          <TextField source="instagram" />
        </FieldGroup>

        <FieldGroup label="Discount (%)" icon={LocalOfferIcon}>
          <TextField source="discount" />
        </FieldGroup>

        <FieldGroup label="Notes" icon={NotesIcon}>
          <TextField source="notes" />
        </FieldGroup>
      </CardWrapper>

      <CardWrapper title="Order History" icon={InventoryIcon}>
        <ReferenceManyField reference="orders" target="client_id">
          <ShowOrderHistory />
        </ReferenceManyField>
      </CardWrapper>
    </SimpleShowLayout>
  </Show>
);
