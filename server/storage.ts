import { type User, type InsertUser } from "@shared/schema";

// Simulation is strictly in-memory for this project as per requirements
// But we keep the storage interface for potential future persistence
export interface IStorage {
  // Empty for now as we use the Simulation class for state
}

export class MemStorage implements IStorage {
  constructor() {}
}

export const storage = new MemStorage();
