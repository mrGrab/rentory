import { Edit, SimpleForm, TextInput, NumberInput } from "react-admin";
import PersonIcon from "@mui/icons-material/Person";
import PhoneIcon from "@mui/icons-material/Phone";
import EmailIcon from "@mui/icons-material/Email";
import InstagramIcon from "@mui/icons-material/Instagram";
import LocalOfferIcon from "@mui/icons-material/LocalOffer";
import NotesIcon from "@mui/icons-material/Notes";
import { CardWrapper } from "../components/Card";

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

export const ClientEdit = () => (
  <Edit title="Edit Client" redirect="show">
    <SimpleForm>
      <CardWrapper title="Information" icon={PersonIcon}>
        <FieldGroup label="Full Name" icon={PersonIcon}>
          <div style={{ display: "flex", gap: "8px" }}>
            <TextInput source="given_name" fullWidth />
            <TextInput source="surname" fullWidth />
          </div>
        </FieldGroup>

        <FieldGroup label="Contact" icon={PhoneIcon}>
          <TextInput source="phone" fullWidth />
        </FieldGroup>

        <FieldGroup label="Email" icon={EmailIcon}>
          <TextInput source="email" fullWidth />
        </FieldGroup>

        <FieldGroup label="Social Media" icon={InstagramIcon}>
          <TextInput source="instagram" fullWidth />
        </FieldGroup>

        <FieldGroup label="Discount" icon={LocalOfferIcon}>
          <NumberInput
            source="discount"
            label="Discount (%)"
            min="0"
            max="100"
            fullWidth
          />{" "}
        </FieldGroup>

        <FieldGroup label="Notes" icon={NotesIcon}>
          <TextInput source="notes" fullWidth multiline rows={3} />
        </FieldGroup>
      </CardWrapper>
    </SimpleForm>
  </Edit>
);
