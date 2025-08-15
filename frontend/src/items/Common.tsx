import { useState } from "react";
import {
  TextInput,
  ArrayInput,
  SimpleFormIterator,
  ImageInput,
  ImageField,
  useDataProvider,
  FormDataConsumer,
  SelectInput,
  NumberInput,
  required,
  TextArrayInput,
  useRecordContext,
} from "react-admin";
import {
  Box,
  FormControl,
  FormLabel,
  RadioGroup,
  FormControlLabel,
  Radio,
  Stack,
} from "@mui/material";
import InfoIcon from "@mui/icons-material/Info";
import InventoryIcon from "@mui/icons-material/Inventory";
import NotesIcon from "@mui/icons-material/Notes";
import { CardWrapper } from "../components/Card";
import { ITEM_STATUS, VARIANT_STATUS } from "../components/Common";

export const useImageHandler = (initialRecord?: any) => {
  const dataProvider = useDataProvider();
  const [imageSource, setImageSource] = useState<"url" | "upload">(() => {
    if (!initialRecord) return "url";
    return initialRecord.image_url ? "url" : "upload";
  });

  const transformImageData = async (data: any) => {
    const processedData = { ...initialRecord, ...data };
    const newImagePayload = processedData.image_payload;

    if (imageSource === "upload") {
      if (newImagePayload?.rawFile instanceof File) {
        try {
          const itemId = initialRecord?.id?.toString();
          processedData.image_url = await dataProvider.uploadImage(
            newImagePayload.rawFile,
            itemId,
          );
        } catch (error) {
          console.error("Image upload failed:", error);
          throw new Error("Image upload failed. Please try again.");
        }
      }
    } else if (imageSource === "url") {
      if (typeof newImagePayload === "string") {
        const url = newImagePayload.trim();
        processedData.image_url = url || null;
      }
    }
    delete processedData.image_payload;
    return processedData;
  };
  return { imageSource, setImageSource, transformImageData };
};

export const EditInfoSection = ({
  imageSource,
  setImageSource,
}: {
  imageSource: "url" | "upload";
  setImageSource: (source: "url" | "upload") => void;
}) => {
  const record = useRecordContext();

  return (
    <CardWrapper title="Core Information" icon={InfoIcon}>
      <Stack direction={{ xs: "column", sm: "row" }} spacing={2}>
        <TextInput
          source="title"
          label="Title"
          fullWidth
          resettable
          validate={required()}
        />
        <TextInput source="category" label="Category" fullWidth resettable />
        <SelectInput
          source="status"
          label="Status"
          defaultValue="in_stock"
          choices={Object.entries(ITEM_STATUS).map(([key, { label }]) => ({
            id: key,
            name: label,
          }))}
          fullWidth
        />
      </Stack>

      <FormControl component="fieldset" sx={{ mt: 2 }}>
        <Box sx={{ display: "flex", alignItems: "center", gap: 2 }}>
          <FormLabel component="legend" sx={{ typography: "body2" }}>
            Image Source:
          </FormLabel>
          <RadioGroup
            row
            value={imageSource}
            onChange={(e) => setImageSource(e.target.value as "url" | "upload")}
          >
            <FormControlLabel
              value="url"
              control={<Radio size="small" />}
              label="URL"
            />
            <FormControlLabel
              value="upload"
              control={<Radio size="small" />}
              label="Upload"
            />
          </RadioGroup>
        </Box>
      </FormControl>

      {imageSource === "upload" ? (
        <ImageInput
          source="image_payload"
          label={false}
          accept={{ "image/*": [".png", ".jpg", ".jpeg", ".gif", ".webp"] }}
        >
          <ImageField source="src" title="title" />
        </ImageInput>
      ) : (
        <>
          <TextInput
            source="image_payload"
            label="Image URL"
            fullWidth
            resettable
            helperText="Provide a direct link to an image."
            defaultValue={record?.image_url}
          />
          <FormDataConsumer>
            {({ formData }) => {
              const imageUrl = formData.image_payload ?? record?.image_url;
              if (!imageUrl) return null;
              return (
                <Box
                  component="img"
                  src={imageUrl}
                  alt="Image Preview"
                  sx={{
                    maxWidth: 100,
                    maxHeight: 100,
                    objectFit: "contain",
                    border: "1px solid",
                    borderColor: "divider",
                    borderRadius: 1,
                    mt: 1,
                  }}
                  onError={(e) => (e.currentTarget.style.display = "none")}
                />
              );
            }}
          </FormDataConsumer>
        </>
      )}
    </CardWrapper>
  );
};
const VariantRow = () => (
  <Box sx={{ pb: 2 }}>
    <Stack direction={{ xs: "column", sm: "row" }} spacing={2} sx={{ mb: 2 }}>
      <TextInput source="size" label="Size" helperText="e.g., S, M, L" />
      <TextInput source="color" label="Color" helperText="e.g., Red, Blue" />
      <SelectInput
        source="status"
        label="Status"
        choices={Object.entries(VARIANT_STATUS).map(([key, { label }]) => ({
          id: key,
          name: label,
        }))}
        defaultValue="available"
        fullWidth
      />{" "}
      <NumberInput
        source="stock_quantity"
        label="Stock"
        defaultValue={1}
        min={1}
      />
    </Stack>

    <ArrayInput source="prices" label="Pricing Tiers">
      <SimpleFormIterator getItemLabel={(index) => `Tier ${index + 1}`}>
        <Stack
          direction={{ xs: "column", sm: "row" }}
          spacing={2}
          sx={{ mb: 1 }}
        >
          <NumberInput
            source="amount"
            label="Amount"
            min={0}
            sx={{ width: "30%" }}
          />
          <TextInput
            source="price_type"
            label="Price Type"
            helperText="e.g., Daily, Weekly"
          />
        </Stack>
      </SimpleFormIterator>
    </ArrayInput>
  </Box>
);

export const EditVariantsSection = () => (
  <CardWrapper title="Variants & Pricing" icon={InventoryIcon}>
    <ArrayInput source="variants" label={false}>
      <SimpleFormIterator getItemLabel={(index) => `Variant ${index + 1}`}>
        <VariantRow />
      </SimpleFormIterator>
    </ArrayInput>
  </CardWrapper>
);

export const EditDetailsSection = () => (
  <CardWrapper title="Additional Details" icon={NotesIcon}>
    <TextInput
      source="description"
      label="Description"
      multiline
      fullWidth
      resettable
      rows={3}
    />
    <TextArrayInput source="tags" label="Tags" />
  </CardWrapper>
);
