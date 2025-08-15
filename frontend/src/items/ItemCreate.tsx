import { Create, SimpleForm } from "react-admin";
import { Stack } from "@mui/material";
import {
  useImageHandler,
  EditInfoSection,
  EditVariantsSection,
  EditDetailsSection,
} from "./Common";

export const ItemCreate = () => {
  const { imageSource, setImageSource, transformImageData } = useImageHandler();

  return (
    <Create transform={transformImageData} redirect="show">
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
    </Create>
  );
};
