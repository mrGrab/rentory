import simpleRestProvider from "ra-data-simple-rest";
import { fetchUtils } from "react-admin";

// API base URL
const API_URL = import.meta.env.VITE_API_BASE_URL;
if (!API_URL) throw new Error("VITE_API_BASE_URL is required");

// Auth-aware fetch
const httpClient = (url: string, options: RequestInit = {}) => {
  const token = localStorage.getItem("token");
  const headers = new Headers(options.headers || {});
  headers.set("Accept", "application/json");
  if (token) headers.set("Authorization", `Bearer ${token}`);
  return fetchUtils.fetchJson(url, { ...options, headers });
};

// Utility to fetch an array from a given endpoint
const fetchList = async (path: string): Promise<string[]> => {
  const { json } = await httpClient(`${API_URL}${path}`);
  return json;
};

// Base provider
const baseProvider = simpleRestProvider(API_URL, httpClient);

// Final provider with extensions
const dataProvider = {
  ...baseProvider,

  // Custom extensions
  getItemCategories: () => fetchList("/items/categories"),
  getItemColors: () => fetchList("/items/colors"),
  getItemSizes: () => fetchList("/items/sizes"),
  getItemStatuses: () => fetchList("/items/statuses"),
  getItemVariantStatuses: () => fetchList("/items/variant_statuses"),

  uploadImage: async (file: File, id: string): Promise<string> => {
    const formData = new FormData();
    formData.append("image", file);
    formData.append("filename", id);

    const token = localStorage.getItem("token");

    const res = await fetch(`${API_URL}/upload/image`, {
      method: "POST",
      body: formData,
      headers: token ? { Authorization: `Bearer ${token}` } : undefined,
    });

    if (!res.ok) {
      const error = await res.json();
      throw new Error(error.detail || "Image upload failed");
    }
    const { image_url } = await res.json();
    return image_url;
  },

  getItemWithAvailability: async (
    id: string,
    params: {
      start_time?: string;
      end_time?: string;
    } = {},
  ) => {
    const query = new URLSearchParams();
    if (params.start_time) query.set("start_time", params.start_time);
    if (params.end_time) query.set("end_time", params.end_time);

    const url = `${API_URL}/items/availability/${id}?${query.toString()}`;
    const { json } = await httpClient(url);
    return json;
  },
};

export default dataProvider;
