import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api, type VehicleType } from "@shared/routes";
import { SimulationStateSchema } from "@shared/schema";

export function useSimulationState() {
  return useQuery({
    queryKey: [api.simulation.getState.path],
    queryFn: async () => {
      const res = await fetch(api.simulation.getState.path);
      if (!res.ok) throw new Error("Failed to fetch simulation state");
      const data = await res.json();
      return SimulationStateSchema.parse(data);
    },
    refetchInterval: 500, // Poll every 500ms for smooth visual updates
  });
}

export function useResetSimulation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      const res = await fetch(api.simulation.reset.path, {
        method: api.simulation.reset.method,
      });
      if (!res.ok) throw new Error("Failed to reset");
      return SimulationStateSchema.parse(await res.json());
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [api.simulation.getState.path] });
    },
  });
}

export function useToggleSimulation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (running: boolean) => {
      const res = await fetch(api.simulation.toggle.path, {
        method: api.simulation.toggle.method,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ running }),
      });
      if (!res.ok) throw new Error("Failed to toggle simulation");
      return await res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [api.simulation.getState.path] });
    },
  });
}

export function useAddVehicle() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ roadId, type }: { roadId: number; type: typeof VehicleType._type }) => {
      const res = await fetch(api.simulation.addVehicle.path, {
        method: api.simulation.addVehicle.method,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ roadId, type }),
      });
      if (!res.ok) throw new Error("Failed to add vehicle");
      return await res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [api.simulation.getState.path] });
    },
  });
}
