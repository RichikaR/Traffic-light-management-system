import { VehicleType, VehicleStatus, type Vehicle as VehicleTypeSchema } from "@shared/schema";
import { v4 as uuidv4 } from 'uuid';

export class Vehicle {
  id: string;
  type: "normal" | "emergency";
  roadId: number;
  arrivalTime: number;
  burstTime: number; // Time needed to cross
  waitTime: number;
  status: "waiting" | "crossing" | "crossed";

  constructor(roadId: number, type: "normal" | "emergency", currentTime: number) {
    this.id = uuidv4();
    this.type = type;
    this.roadId = roadId;
    this.arrivalTime = currentTime;
    this.burstTime = 1; // Assuming 1 second to cross for simplicity
    this.waitTime = 0;
    this.status = "waiting";
  }

  toJSON(): VehicleTypeSchema {
    return {
      id: this.id,
      type: this.type,
      roadId: this.roadId,
      arrivalTime: this.arrivalTime,
      burstTime: this.burstTime,
      waitTime: this.waitTime,
      status: this.status,
    };
  }
}
