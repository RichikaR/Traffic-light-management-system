import { Vehicle } from "./vehicle";
import { type Road as RoadTypeSchema } from "@shared/schema";

export class Road {
  id: number;
  name: string;
  queue: Vehicle[];
  isGreen: boolean;
  greenTimeRemaining: number;
  quantum: number; // Time quantum for Round Robin

  constructor(id: number, name: string, quantum: number = 5) {
    this.id = id;
    this.name = name;
    this.queue = [];
    this.isGreen = false;
    this.greenTimeRemaining = 0;
    this.quantum = quantum;
  }

  addVehicle(vehicle: Vehicle) {
    this.queue.push(vehicle);
    // Sort queue: Emergency vehicles have absolute priority
    this.queue.sort((a, b) => {
      if (a.type === 'emergency' && b.type !== 'emergency') return -1;
      if (a.type !== 'emergency' && b.type === 'emergency') return 1;
      return a.arrivalTime - b.arrivalTime; // FIFO for same priority
    });
  }

  hasEmergency(): boolean {
    return this.queue.some(v => v.type === 'emergency');
  }

  toJSON(): RoadTypeSchema {
    return {
      id: this.id,
      name: this.name,
      queue: this.queue.map(v => v.toJSON()),
      isGreen: this.isGreen,
      greenTimeRemaining: this.greenTimeRemaining,
    };
  }
}
