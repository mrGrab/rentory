import { Edit, SimpleForm, useRecordContext } from "react-admin";
import { Stack } from "@mui/material";
import {
  useImageHandler,
  EditInfoSection,
  EditVariantsSection,
  EditDetailsSection,
} from "./Common";

export const ItemEdit = () => {
  const record = useRecordContext();
  console.log("Editing item:", record);
  const { imageSource, setImageSource, transformImageData } =
    useImageHandler(record);

  return (
    <Edit transform={transformImageData} redirect="show">
      <SimpleForm>
        <Stack spacing={3}>
          <EditInfoSection
            imageSource={imageSource}
            setImageSource={setImageSource}
          />
          <EditVariantsSection />
          <EditDetailsSection />
        </Stack>
      </SimpleForm>
    </Edit>
  );
};
