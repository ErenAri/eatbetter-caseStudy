export type HealthResponse = {
  status: "ok";
  mode: "demo" | "live" | "unconfigured";
  providers: { vision: "demo" | "openai"; canonicalization: "demo" | "openai"; nutrition: "demo" | "usda" };
};
export type BackendHealth = { status: "loading" | "connected" | "unavailable"; label: string };
