import { pgTable, text, serial, integer, boolean, timestamp, jsonb } from "drizzle-orm/pg-core";
import { createInsertSchema } from "drizzle-zod";
import { z } from "zod";

// We primarily use in-memory state for the simulation, 
// but we define the shared types here for consistency.

export const VehicleType = z.enum(["normal", "emergency"]);
export const VehicleStatus = z.enum(["waiting", "crossing", "crossed"]);

export const VehicleSchema = z.object({
  id: z.string(),
  type: VehicleType,
  roadId: z.number(), // 0: North, 1: East, 2: South, 3: West
  arrivalTime: z.number(),
  burstTime: z.number(), // Time required to cross
  waitTime: z.number(),
  status: VehicleStatus,
});

export const RoadSchema = z.object({
  id: z.number(),
  name: z.string(),
  queue: z.array(VehicleSchema),
  isGreen: z.boolean(),
  greenTimeRemaining: z.number(), // For Round Robin quantum
});

export const SimulationMetricsSchema = z.object({
  totalVehiclesProcessed: z.number(),
  averageWaitTime: z.number(),
  averageTurnaroundTime: z.number(),
  cpuUtilization: z.number(), // % of time intersection is busy
});

export const SimulationStateSchema = z.object({
  roads: z.array(RoadSchema),
  currentTime: z.number(),
  activeRoadId: z.number().nullable(),
  isEmergencyActive: z.boolean(), // Interrupt active
  isRunning: z.boolean(),
  metrics: SimulationMetricsSchema,
  logs: z.array(z.string()), // System logs (e.g., "Context Switch to North")
});

export type Vehicle = z.infer<typeof VehicleSchema>;
export type Road = z.infer<typeof RoadSchema>;
export type SimulationState = z.infer<typeof SimulationStateSchema>;
export type SimulationMetrics = z.infer<typeof SimulationMetricsSchema>;
