import React from "react";
import {
  Create,
  SimpleForm,
  TextInput,
  required,
  email,
  maxLength,
  useNotify,
  useRedirect,
  SaveButton,
  Toolbar,
  NumberInput,
} from "react-admin";
import PersonIcon from "@mui/icons-material/Person";
import PhoneIcon from "@mui/icons-material/Phone";
import EmailIcon from "@mui/icons-material/Email";
import InstagramIcon from "@mui/icons-material/Instagram";
import LocalOfferIcon from "@mui/icons-material/LocalOffer";
import NotesIcon from "@mui/icons-material/Notes";
import { CardWrapper } from "../components/Card";

const ClientCreateToolbar = () => (
  <Toolbar>
    <SaveButton label="Create Client" variant="contained" size="large" />
  </Toolbar>
);

type FieldGroupProps = {
  label: string;
  children: React.ReactNode;
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

export const ClientCreate = () => {
  const notify = useNotify();
  const redirect = useRedirect();

  const handleSuccess = () => {
    notify("Client created successfully!", { type: "success" });
    redirect("list", "clients");
  };

  const handleError = (error: any) => {
    notify(
      error?.body?.message || "Failed to create client. Please try again.",
      { type: "error" },
    );
  };

  return (
    <Create
      title="New Client Registration"
      mutationOptions={{ onSuccess: handleSuccess, onError: handleError }}
    >
      <SimpleForm toolbar={<ClientCreateToolbar />}>
        <CardWrapper title="Information" icon={PersonIcon}>
          <FieldGroup label="Full Name" icon={PersonIcon}>
            <div style={{ display: "flex", gap: "8px" }}>
              <TextInput
                source="given_name"
                label="First Name"
                validate={required()}
                fullWidth
              />
              <TextInput source="surname" label="Last Name" fullWidth />
            </div>
          </FieldGroup>

          <FieldGroup label="Contact" icon={PhoneIcon}>
            <TextInput
              source="phone"
              label="Phone Number"
              validate={required()}
              fullWidth
            />
          </FieldGroup>

          <FieldGroup label="Email" icon={EmailIcon}>
            <TextInput
              source="email"
              label="Email Address"
              validate={[email(), maxLength(255)]}
              fullWidth
            />
          </FieldGroup>

          <FieldGroup label="Social Media" icon={InstagramIcon}>
            <TextInput source="instagram" label="Instagram" fullWidth />
          </FieldGroup>

          <FieldGroup label="Discount" icon={LocalOfferIcon}>
            <NumberInput
              source="discount"
              label="Discount (%)"
              min="0"
              max="100"
              fullWidth
            />
          </FieldGroup>

          <FieldGroup label="Notes" icon={NotesIcon}>
            <TextInput
              source="notes"
              label="Notes"
              multiline
              resettable
              fullWidth
              rows={3}
              validate={maxLength(512)}
            />
          </FieldGroup>
        </CardWrapper>
      </SimpleForm>
    </Create>
  );
};
