import { useEffect, useState } from "react";

import { getHealth } from "../services/api";
import { BackendHealthStatus } from "../types/health";


export function useBackendHealth(): BackendHealthStatus {
  const [status, setStatus] = useState<BackendHealthStatus>("loading");

  useEffect(() => {
    let active = true;
    getHealth()
      .then((response) => {
        if (active) setStatus(response.status === "ok" ? "connected" : "unavailable");
      })
      .catch(() => {
        if (active) setStatus("unavailable");
      });
    return () => { active = false; };
  }, []);

  return status;
}
