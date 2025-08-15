import {
  Datagrid,
  List,
  ReferenceField,
  FunctionField,
  TopToolbar,
  useUpdate,
  useNotify,
  useRefresh,
  Form,
  ReferenceInput,
  AutocompleteInput,
  DateInput,
  SaveButton,
  required,
  SelectInput,
  useDataProvider,
  RaRecord,
  Button,
  FilterButton,
  ReferenceArrayInput,
  AutocompleteArrayInput,
} from "react-admin";
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Stack,
  Chip,
  CircularProgress,
} from "@mui/material";
import { useState, useEffect } from "react";
import { useWatch } from "react-hook-form";
import { VariantStatusChip, ShowDateField } from "../components/Common";
import DeleteIcon from "@mui/icons-material/Delete";
import EditIcon from "@mui/icons-material/Edit";

interface Variant extends RaRecord {
  id: string;
  size?: string;
  color?: string;
}

const formatVariantName = (variant: { size?: string; color?: string }) => {
  const parts = [variant.size, variant.color].filter(Boolean);
  return parts.length > 0 ? parts.join(" ") : "Default";
};

const DialogFormContent = ({ record }: { record?: any }) => {
  const itemId = useWatch({ name: "item_id" });
  const [variants, setVariants] = useState<Variant[]>([]);
  const [isLoadingVariants, setLoadingVariants] = useState(false);
  const dataProvider = useDataProvider();

  useEffect(() => {
    const targetItemId = itemId || record?.item_id;
    if (!targetItemId) return setVariants([]);

    setLoadingVariants(true);
    dataProvider
      .getOne("items", { id: targetItemId })
      .then(({ data }) => setVariants(data.variants || []))
      .finally(() => setLoadingVariants(false));
  }, [itemId, record?.item_id, dataProvider]);

  const variantChoices = variants.map((v) => ({
    id: v.id,
    name: formatVariantName(v),
  }));

  const endDateAfterStart = (value: any, allValues: any) => {
    if (!value || !allValues.service_start_time) return undefined;
    return new Date(value) >= new Date(allValues.service_start_time)
      ? undefined
      : "End date must be after start date";
  };

  return (
    <Stack spacing={2} sx={{ mt: 1 }}>
      <ReferenceInput source="item_id" reference="items">
        <AutocompleteInput
          optionText="title"
          label="Item"
          validate={required()}
          fullWidth
        />
      </ReferenceInput>

      {isLoadingVariants && <CircularProgress size={24} />}

      <SelectInput
        source="variant_id"
        label="Variant"
        choices={variantChoices}
        disabled={isLoadingVariants || variantChoices.length === 0}
        validate={required()}
        fullWidth
      />

      <SelectInput
        source="status"
        label="Status"
        choices={[
          { id: "repair", name: "REPAIR" },
          { id: "cleaning", name: "CLEANING" },
        ]}
        validate={required()}
        fullWidth
      />

      <DateInput
        source="service_start_time"
        label="Start"
        validate={required()}
        fullWidth
      />
      <DateInput
        source="service_end_time"
        label="End"
        validate={[required(), endDateAfterStart]}
        fullWidth
      />
    </Stack>
  );
};

const VariantDialog = ({
  open,
  onClose,
  onSave,
  record,
}: {
  open: boolean;
  onClose: () => void;
  onSave: (data: any) => void;
  record?: any;
}) => {
  const handleSubmit = async (formData: any) => {
    const finalData = {
      id: record?.id || formData.variant_id,
      item_id: formData.item_id,
      status: formData.status,
      service_start_time: formData.service_start_time,
      service_end_time: formData.service_end_time,
    };
    onSave(finalData);
  };

  const defaultValues = record
    ? {
        item_id: record.item_id,
        variant_id: record.variant_id || record.id,
        status: record.status || record.status,
        service_start_time: record.service_start_time,
        service_end_time: record.service_end_time,
      }
    : {};

  return (
    <Dialog open={open} onClose={onClose} maxWidth="xs" fullWidth>
      <Form
        onSubmit={handleSubmit}
        defaultValues={defaultValues}
        key={record?.id || "new"}
      >
        <DialogTitle>{record ? "Edit Variant" : "Add Variant"}</DialogTitle>
        <DialogContent>
          <DialogFormContent record={record} />
        </DialogContent>
        <DialogActions>
          <Button color="secondary" onClick={onClose}>
            Cancel
          </Button>
          <SaveButton />
        </DialogActions>
      </Form>
    </Dialog>
  );
};

const VariantActions = ({
  record,
  onEdit,
}: {
  record: any;
  onEdit: (record: any) => void;
}) => {
  const [update] = useUpdate();
  const notify = useNotify();
  const refresh = useRefresh();

  const handleRemove = () => {
    update(
      "variants",
      { id: record.id, data: { status: "available" } },
      {
        onSuccess: () => {
          notify("Variant removed from service.", { type: "info" });
          refresh();
        },
        onError: () =>
          notify("Error: Unable to update variant.", { type: "error" }),
      },
    );
  };

  return (
    <Stack direction="row" spacing={1} justifyContent="right">
      <Button
        label="Edit"
        variant="outlined"
        disableElevation
        size="small"
        startIcon={<EditIcon />}
        onClick={() => onEdit(record)}
      />
      <Button
        label="Remove"
        variant="outlined"
        disableElevation
        size="small"
        startIcon={<DeleteIcon />}
        onClick={handleRemove}
      />
    </Stack>
  );
};

const ListActions = ({ onAddClick }: { onAddClick: () => void }) => (
  <TopToolbar>
    <FilterButton />
    <Button onClick={onAddClick}>Add items</Button>
  </TopToolbar>
);

const variantFilters = [
  <DateInput key="date" label="Service end" source="service_end_time" />,
  <ReferenceArrayInput
    key="items"
    source="item_id"
    reference="items"
    label="Items"
  >
    <AutocompleteArrayInput optionText="title" />
  </ReferenceArrayInput>,
];

export const VariantList = () => {
  const [open, setOpen] = useState(false);
  const [editingRecord, setEditingRecord] = useState<any | null>(null);
  const notify = useNotify();
  const refresh = useRefresh();
  const [update] = useUpdate();

  const handleSave = (data: any) => {
    update(
      "variants",
      { id: data.id, data },
      {
        onSuccess: () => {
          notify("Variant saved successfully.", { type: "success" });
          setOpen(false);
          setEditingRecord(null);
          refresh();
        },
        onError: () =>
          notify("Error: Unable to save variant", { type: "error" }),
      },
    );
  };

  const handleEditClick = (record: any) => {
    setEditingRecord(record);
    setOpen(true);
  };

  const handleAddClick = () => {
    setEditingRecord(null);
    setOpen(true);
  };

  const handleClose = () => {
    setOpen(false);
    setEditingRecord(null);
  };

  return (
    <>
      <List
        actions={<ListActions onAddClick={handleAddClick} />}
        filter={{ status: ["repair", "cleaning"] }}
        filters={variantFilters}
      >
        <Datagrid rowClick={false}>
          <ReferenceField source="item_id" reference="items" link="show">
            <FunctionField
              render={(item: any) => (
                <Chip
                  label={`${item.title} ${item.category || ""}`}
                  clickable
                  color="info"
                  size="small"
                />
              )}
            />
          </ReferenceField>

          <FunctionField
            label="Variant"
            render={(record: any) =>
              record
                ? `${record.size || ""} ${record.color || ""}`.trim()
                : "Default"
            }
          />
          <ShowDateField source="service_start_time" label="Start" />
          <ShowDateField source="service_end_time" label="End" />
          <FunctionField
            label="Status"
            render={() => <VariantStatusChip />}
            sortBy="status"
          />

          {/* Actions column aligned right */}
          <FunctionField
            label="Actions"
            render={(record: any) => (
              <VariantActions record={record} onEdit={handleEditClick} />
            )}
            sortable={false}
          />
        </Datagrid>
      </List>

      <VariantDialog
        open={open}
        onClose={handleClose}
        onSave={handleSave}
        record={editingRecord}
      />
    </>
  );
};
