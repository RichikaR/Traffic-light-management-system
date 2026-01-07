import { useState } from "react";
import { useSimulationState, useResetSimulation, useToggleSimulation, useAddVehicle } from "@/hooks/use-simulation";
import { Visualizer } from "@/components/Visualizer";
import { TerminalLog } from "@/components/TerminalLog";
import { MetricCard } from "@/components/MetricCard";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { 
  Activity, 
  Timer, 
  RotateCcw, 
  Play, 
  Pause, 
  Plus, 
  Siren, 
  Cpu,
  Car
} from "lucide-react";
import { motion } from "framer-motion";

export default function Dashboard() {
  const { data: state, isLoading, error } = useSimulationState();
  const reset = useResetSimulation();
  const toggle = useToggleSimulation();
  const addVehicle = useAddVehicle();

  const [selectedRoad, setSelectedRoad] = useState<string>("0");

  if (isLoading) {
    return (
      <div className="h-screen w-full flex items-center justify-center bg-background text-foreground font-mono">
        <div className="flex flex-col items-center gap-4 animate-pulse">
          <Cpu size={48} className="text-primary" />
          <p>INITIALIZING KERNEL...</p>
        </div>
      </div>
    );
  }

  if (error || !state) {
    return (
      <div className="h-screen w-full flex items-center justify-center bg-background text-red-500 font-mono">
        KERNEL PANIC: Connection failed.
      </div>
    );
  }

  const handleAddVehicle = (type: "normal" | "emergency") => {
    addVehicle.mutate({ roadId: parseInt(selectedRoad), type });
  };

  return (
    <div className="min-h-screen bg-background text-foreground p-4 md:p-8 flex flex-col gap-6">
      
      {/* HEADER */}
      <header className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-border/50 pb-6">
        <div>
          <h1 className="text-3xl font-bold tracking-tight font-mono text-glow text-primary flex items-center gap-3">
            <Activity className="text-emerald-500" />
            OS_SCHEDULER_SIM_v1.0
          </h1>
          <p className="text-muted-foreground mt-1 max-w-2xl text-sm font-mono">
            Traffic Control System implementing Round Robin Scheduling with Priority Preemption.
            <span className="ml-2 text-primary/60">Intersection = CPU, Roads = Ready Queues, Vehicles = Processes.</span>
          </p>
        </div>

        <div className="flex items-center gap-2">
           <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-muted/50 border border-border">
             <div className={`w-2 h-2 rounded-full ${state.isRunning ? 'bg-emerald-500 animate-pulse' : 'bg-red-500'}`} />
             <span className="text-xs font-mono font-bold">{state.isRunning ? 'RUNNING' : 'HALTED'}</span>
           </div>
        </div>
      </header>

      {/* METRICS ROW */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard 
          label="Total Processes" 
          value={state.metrics.totalVehiclesProcessed} 
          icon={Car} 
          color="blue" 
          subtext="Vehicles Crossed"
        />
        <MetricCard 
          label="Avg Wait Time" 
          value={`${state.metrics.averageWaitTime.toFixed(1)}s`} 
          icon={Timer} 
          color="yellow"
          subtext="Ready Queue Latency" 
        />
        <MetricCard 
          label="CPU Utilization" 
          value={`${state.metrics.cpuUtilization.toFixed(1)}%`} 
          icon={Cpu} 
          color="green"
          subtext="Intersection Busy Time"
        />
        <MetricCard 
          label="Context Switches" 
          value={state.logs.filter(l => l.includes("Switch")).length} 
          icon={RotateCcw} 
          color="red"
          subtext="OS Overhead"
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 flex-1 min-h-[500px]">
        
        {/* MAIN VISUALIZER */}
        <div className="lg:col-span-2 flex flex-col gap-4">
          <Card className="flex-1 bg-black/20 border-white/5 p-1 overflow-hidden relative group">
             <Visualizer state={state} />
             
             {/* SIMULATION TIME OVERLAY */}
             <div className="absolute top-4 left-4 bg-background/80 backdrop-blur border border-border px-3 py-1 rounded font-mono text-xs">
               SYSTEM_TIME: {state.currentTime.toFixed(1)}s
             </div>
          </Card>

          {/* CONTROLS */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Control Panel */}
            <Card className="p-4 bg-card/50 backdrop-blur border-white/5 space-y-4">
              <div className="flex items-center gap-2 mb-2">
                <div className="w-1 h-4 bg-primary rounded-full" />
                <h3 className="font-mono font-bold text-sm">PROCESS MANAGEMENT</h3>
              </div>
              
              <div className="flex gap-2">
                <Select value={selectedRoad} onValueChange={setSelectedRoad}>
                  <SelectTrigger className="w-[140px] font-mono">
                    <SelectValue placeholder="Select Queue" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="0">North Queue</SelectItem>
                    <SelectItem value="1">East Queue</SelectItem>
                    <SelectItem value="2">South Queue</SelectItem>
                    <SelectItem value="3">West Queue</SelectItem>
                  </SelectContent>
                </Select>
                
                <Button 
                  onClick={() => handleAddVehicle("normal")}
                  disabled={addVehicle.isPending}
                  variant="secondary"
                  className="flex-1 font-mono hover:bg-blue-500/20 hover:text-blue-400 transition-colors"
                >
                  <Plus size={16} className="mr-2" />
                  Add Process
                </Button>
                
                <Button 
                  onClick={() => handleAddVehicle("emergency")}
                  disabled={addVehicle.isPending}
                  variant="destructive"
                  className="w-12 px-0 hover:animate-pulse"
                  title="Generate Hardware Interrupt (Emergency)"
                >
                  <Siren size={18} />
                </Button>
              </div>
            </Card>

            {/* System Control */}
            <Card className="p-4 bg-card/50 backdrop-blur border-white/5 space-y-4">
               <div className="flex items-center gap-2 mb-2">
                <div className="w-1 h-4 bg-red-500 rounded-full" />
                <h3 className="font-mono font-bold text-sm">KERNEL CONTROL</h3>
              </div>

              <div className="flex gap-2">
                <Button 
                   className={state.isRunning ? "bg-amber-600 hover:bg-amber-700" : "bg-emerald-600 hover:bg-emerald-700"}
                   onClick={() => toggle.mutate(!state.isRunning)}
                   disabled={toggle.isPending}
                 >
                   {state.isRunning ? <Pause className="mr-2" size={16} /> : <Play className="mr-2" size={16} />}
                   {state.isRunning ? "Suspend Scheduler" : "Start Scheduler"}
                 </Button>

                 <Button 
                   variant="outline" 
                   onClick={() => reset.mutate()}
                   disabled={reset.isPending}
                   className="hover:bg-red-500/20 hover:text-red-500 border-white/10"
                 >
                   <RotateCcw size={16} />
                 </Button>
              </div>
            </Card>
          </div>
        </div>

        {/* LOGS SIDEBAR */}
        <div className="h-[400px] lg:h-auto min-h-0">
          <TerminalLog logs={state.logs} />
        </div>

      </div>
    </div>
  );
}
