const apiBaseUrl = import.meta.env.VITE_API_BASE_URL;
if (!apiBaseUrl) {
  throw new Error("VITE_API_BASE_URL is not defined");
}

const getToken = (): string | null => localStorage.getItem("token");
const setToken = (token: string): void => localStorage.setItem("token", token);
const removeToken = (): void => localStorage.removeItem("token");

interface LoginParams {
  username: string;
  password: string;
}

interface CheckErrorParams {
  status: number;
}

export const authProvider = {
  login: async ({ username, password }: LoginParams): Promise<void> => {
    try {
      const response = await fetch(`${apiBaseUrl}/login/access-token`, {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: new URLSearchParams({ username, password }),
      });

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`Login failed: ${response.status} ${errorText}`);
      }

      const { access_token } = await response.json();
      setToken(access_token);
      return Promise.resolve();
    } catch (error) {
      console.error("[Auth] Login error:", error);
      return Promise.reject(error);
    }
  },

  logout: (): Promise<void> => {
    removeToken();
    return Promise.resolve();
  },

  checkAuth: (): Promise<void> => {
    return getToken() ? Promise.resolve() : Promise.reject();
  },

  checkError: ({ status }: CheckErrorParams): Promise<void> => {
    if (status === 401 || status === 403) {
      removeToken();
      return Promise.reject();
    }
    return Promise.resolve();
  },

  getPermissions: (): Promise<void> => Promise.resolve(),
};
