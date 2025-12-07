/**
 * Application configuration
 * Validates and provides type-safe access to environment variables
 */

interface Config {
  api: {
    baseURL: string;
  };
  midtrans: {
    clientKey: string;
  };
  app: {
    url: string;
    environment: "development" | "production" | "staging";
  };
}

function getConfig(): Config {
  const apiURL = process.env.NEXT_PUBLIC_API_URL;
  const midtransClientKey = process.env.NEXT_PUBLIC_MIDTRANS_CLIENT_KEY;
  const appURL = process.env.NEXT_PUBLIC_APP_URL;
  const environment = process.env.NEXT_PUBLIC_ENVIRONMENT;

  // Validate required variables
  if (!apiURL) {
    throw new Error("NEXT_PUBLIC_API_URL is not defined");
  }

  return {
    api: {
      baseURL: apiURL,
    },
    midtrans: {
      clientKey: midtransClientKey || "",
    },
    app: {
      url: appURL || "http://localhost:3000",
      environment: (environment as Config["app"]["environment"]) || "development",
    },
  };
}

export const config = getConfig();
