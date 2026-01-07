import type { Express } from "express";
import type { Server } from "http";
import { api } from "@shared/routes";
import { scheduler } from "./simulation/scheduler";
import { z } from "zod";

export async function registerRoutes(
  httpServer: Server,
  app: Express
): Promise<Server> {
  
  // Get Simulation State
  app.get(api.simulation.getState.path, (_req, res) => {
    res.json(scheduler.getState());
  });

  // Reset Simulation
  app.post(api.simulation.reset.path, (_req, res) => {
    scheduler.reset();
    res.json(scheduler.getState());
  });

  // Toggle Start/Stop
  app.post(api.simulation.toggle.path, (req, res) => {
    const input = api.simulation.toggle.input.parse(req.body);
    scheduler.isRunning = input.running;
    scheduler.log(input.running ? "Simulation Resumed" : "Simulation Paused");
    res.json({ running: scheduler.isRunning });
  });

  // Add Vehicle
  app.post(api.simulation.addVehicle.path, (req, res) => {
    const input = api.simulation.addVehicle.input.parse(req.body);
    scheduler.addVehicle(input.roadId, input.type);
    res.status(201).json({ message: "Vehicle added" });
  });

  return httpServer;
}
