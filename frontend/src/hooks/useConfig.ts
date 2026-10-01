import { useCallback, useEffect, useState } from "react";
import { fetchConfig } from "../api/client";
import type { InvitationConfig } from "../types/config";

export type ConfigStatus = "loading" | "success" | "error";

export function useConfig() {
  const [config, setConfig] = useState<InvitationConfig | null>(null);
  const [status, setStatus] = useState<ConfigStatus>("loading");
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setStatus("loading");
    setError(null);
    try {
      const data = await fetchConfig();
      setConfig(data);
      setStatus("success");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error al cargar la configuración");
      setStatus("error");
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  return { config, status, error, reload: load };
}
