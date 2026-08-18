const configuredApiUrl = process.env.EXPO_PUBLIC_API_URL?.trim();

export const API_BASE_URL = (configuredApiUrl || "http://127.0.0.1:8000").replace(/\/$/, "");
