import { useEffect, useState } from "react";

import { getHealth } from "../services/api";
import { BackendHealth } from "../types/health";


export function useBackendHealth(): BackendHealth {
  const [health, setHealth] = useState<BackendHealth>({ status: "loading", label: "Connecting" });

  useEffect(() => {
    let active = true;
    getHealth()
      .then((response) => {
        if (active) setHealth({ status: "connected", label: response.mode === "live" ? "Live providers" : response.mode === "demo" ? "Demo providers" : "Provider setup needed" });
      })
      .catch(() => {
        if (active) setHealth({ status: "unavailable", label: "API offline" });
      });
    return () => { active = false; };
  }, []);

  return health;
}
