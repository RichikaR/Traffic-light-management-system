import { Road } from "./road";
import { Vehicle } from "./vehicle";
import { type SimulationState, type SimulationMetrics } from "@shared/schema";

export class TrafficScheduler {
  roads: Road[];
  currentTime: number;
  activeRoadIndex: number | null;
  isRunning: boolean;
  logs: string[];
  metrics: SimulationMetrics;
  
  // OS Concept: Context Switch Overhead
  isContextSwitching: boolean;
  contextSwitchTimer: number;
  CONTEXT_SWITCH_TIME = 2; // 2 seconds yellow light

  // OS Concept: Interrupt Flag
  interruptActive: boolean;

  constructor() {
    this.roads = [
      new Road(0, "North"),
      new Road(1, "East"),
      new Road(2, "South"),
      new Road(3, "West")
    ];
    this.currentTime = 0;
    this.activeRoadIndex = null;
    this.isRunning = false;
    this.logs = [];
    this.isContextSwitching = false;
    this.contextSwitchTimer = 0;
    this.interruptActive = false;
    
    this.metrics = {
      totalVehiclesProcessed: 0,
      averageWaitTime: 0,
      averageTurnaroundTime: 0,
      cpuUtilization: 0
    };

    this.log("System Initialized. Scheduler: Round Robin + Priority Preemption.");
  }

  log(message: string) {
    const timestamp = new Date().toISOString().split('T')[1].split('.')[0];
    this.logs.unshift(`[T=${this.currentTime}s] ${message}`);
    if (this.logs.length > 50) this.logs.pop();
  }

  addVehicle(roadId: number, type: "normal" | "emergency") {
    const road = this.roads[roadId];
    if (road) {
      const vehicle = new Vehicle(roadId, type, this.currentTime);
      road.addVehicle(vehicle);
      this.log(`New Process (Vehicle) Created: ID=${vehicle.id.slice(0, 4)} Type=${type} on ${road.name}`);
      
      // Interrupt: If emergency added, trigger check immediately
      if (type === 'emergency') {
        this.checkForInterrupts();
      }
    }
  }

  checkForInterrupts() {
    // Check if any road (other than current) has emergency
    let emergencyRoadIndex = -1;
    
    for (let i = 0; i < this.roads.length; i++) {
      if (this.roads[i].hasEmergency()) {
        emergencyRoadIndex = i;
        break; // Take the first one found
      }
    }

    if (emergencyRoadIndex !== -1 && emergencyRoadIndex !== this.activeRoadIndex) {
      this.log(`HARDWARE INTERRUPT: Emergency on ${this.roads[emergencyRoadIndex].name}. Preempting current process.`);
      this.interruptActive = true;
      this.triggerContextSwitch(emergencyRoadIndex);
    }
  }

  triggerContextSwitch(nextRoadIndex: number) {
    if (this.activeRoadIndex !== null) {
      this.roads[this.activeRoadIndex].isGreen = false;
      this.roads[this.activeRoadIndex].greenTimeRemaining = 0;
    }
    
    this.isContextSwitching = true;
    this.contextSwitchTimer = this.CONTEXT_SWITCH_TIME;
    this.activeRoadIndex = nextRoadIndex; // Prepare switch
    
    // Reset waitCount for the road getting green
    this.roads[nextRoadIndex].waitCount = 0;
    
    this.log(`Context Switch Initiated... (Yellow Light for ${this.CONTEXT_SWITCH_TIME}s)`);
  }

  tick() {
    if (!this.isRunning) return;

    this.currentTime++;

    // 1. Handle Context Switching (Yellow Light)
    if (this.isContextSwitching) {
      this.contextSwitchTimer--;
      if (this.contextSwitchTimer <= 0) {
        this.isContextSwitching = false;
        if (this.activeRoadIndex !== null) {
          this.roads[this.activeRoadIndex].isGreen = true;
          this.roads[this.activeRoadIndex].greenTimeRemaining = this.roads[this.activeRoadIndex].quantum;
          this.log(`Context Switch Complete. CPU granted to ${this.roads[this.activeRoadIndex].name}. Quantum=${this.roads[this.activeRoadIndex].quantum}s`);
        }
      }
      return; // No processing during context switch
    }

    // 2. Start Initial Process if Idle
    if (this.activeRoadIndex === null) {
      this.triggerContextSwitch(0);
      return;
    }

    const activeRoad = this.roads[this.activeRoadIndex];

    // 3. Process Vehicle (CPU Execution)
    if (activeRoad.queue.length > 0) {
      const vehicle = activeRoad.queue[0];
      vehicle.status = 'crossing';
      
      // Assume 1 vehicle passes per second for simplicity
      this.log(`CPU Executing Process ${vehicle.id.slice(0, 4)} from ${activeRoad.name}`);
      
      // Vehicle Completed
      activeRoad.queue.shift(); // Remove from queue
      this.updateMetrics(vehicle);
    } else {
      this.log(`CPU Idle on ${activeRoad.name} (Ready Queue Empty)`);
    }

    // 4. Update Waiting Times for other processes
    this.roads.forEach(road => {
      road.queue.forEach(v => {
        if (v.status === 'waiting') {
          v.waitTime++;
        }
      });
    });

    // 5. Check Quantum Expiry or Interrupts
    activeRoad.greenTimeRemaining--;
    
    // Check for interrupts (Emergency on other roads)
    let emergencyPending = false;
    for (let i = 0; i < this.roads.length; i++) {
      if (i !== this.activeRoadIndex && this.roads[i].hasEmergency()) {
        this.log(`INTERRUPT: Emergency detected on ${this.roads[i].name}!`);
        this.triggerContextSwitch(i);
        emergencyPending = true;
        break;
      }
    }

    if (!emergencyPending) {
      // Max-Pressure (Aging) Logic
      // 1. Skip Empty Roads
      // 2. Variable Timing (2s per vehicle, min 4s, max 10s)
      
      if (activeRoad.greenTimeRemaining <= 0 || activeRoad.queue.length === 0) {
        if (activeRoad.greenTimeRemaining <= 0) {
          this.log(`Quantum Expired for ${activeRoad.name}. Re-evaluating Demand...`);
        } else {
          this.log(`Ready Queue Empty on ${activeRoad.name}. Yielding CPU.`);
        }

        // Find road with MAX EFFECTIVE PRESSURE (queue + waitCount)
        let maxEffectivePressure = -1;
        let nextRoadIndex = -1;

        for (let i = 0; i < this.roads.length; i++) {
          const road = this.roads[i];
          const effectivePressure = road.queue.length + road.waitCount;
          
          if (effectivePressure > 0 && effectivePressure > maxEffectivePressure) {
            maxEffectivePressure = effectivePressure;
            nextRoadIndex = i;
          }
        }

        if (nextRoadIndex !== -1) {
          // Aging & Reset logic
          for (let i = 0; i < this.roads.length; i++) {
            if (i === nextRoadIndex) {
              this.roads[i].waitCount = 0; // Reset selected
            } else {
              this.roads[i].waitCount += 1; // Increment others
            }
          }

          // Dynamic Quantum Calculation (2s per vehicle, min 4s, max 10s)
          const road = this.roads[nextRoadIndex];
          const dynamicQuantum = Math.min(Math.max(road.queue.length * 2, 4), 10);
          road.quantum = dynamicQuantum;
          
          this.log(`Max-Pressure (Aging): Selecting ${road.name} (Queue=${road.queue.length}, WaitCount=${this.roads[nextRoadIndex].waitCount}). Effective Pressure=${maxEffectivePressure}. Quantum=${dynamicQuantum}s`);
          this.triggerContextSwitch(nextRoadIndex);
        } else {
          // All roads empty and no wait counts
          this.activeRoadIndex = null;
          this.log("All Ready Queues empty. System entering IDLE state.");
        }
      }
    }
  }

  updateMetrics(vehicle: Vehicle) {
    this.metrics.totalVehiclesProcessed++;
    // Turnaround = Completion Time - Arrival Time
    // Completion Time = Current Time
    const turnaround = this.currentTime - vehicle.arrivalTime;
    
    // Weighted moving average for smoothness
    const n = this.metrics.totalVehiclesProcessed;
    this.metrics.averageWaitTime = ((this.metrics.averageWaitTime * (n - 1)) + vehicle.waitTime) / n;
    this.metrics.averageTurnaroundTime = ((this.metrics.averageTurnaroundTime * (n - 1)) + turnaround) / n;
  }

  getState(): SimulationState {
    return {
      roads: this.roads.map(r => r.toJSON()),
      currentTime: this.currentTime,
      activeRoadId: this.activeRoadIndex,
      isEmergencyActive: this.interruptActive,
      isRunning: this.isRunning,
      metrics: this.metrics,
      logs: this.logs
    };
  }

  reset() {
    this.constructor(); // Re-init
  }
}

// Singleton Instance
export const scheduler = new TrafficScheduler();

// Start the clock loop
setInterval(() => {
  scheduler.tick();
}, 1000); // 1 second real-time = 1 second simulation time
