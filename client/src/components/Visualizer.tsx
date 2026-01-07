import { motion, AnimatePresence } from "framer-motion";
import { type Road, type Vehicle, type SimulationState } from "@shared/schema";
import { cn } from "@/lib/utils";
import { Cpu, AlertOctagon, CarFront, Zap, Clock } from "lucide-react";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

interface VisualizerProps {
  state: SimulationState;
}

// OS Metaphor Helper
const RoadLabel = ({ name, id }: { name: string; id: number }) => (
  <div className="absolute font-mono text-xs font-bold tracking-widest text-muted-foreground/60 uppercase">
    QUEUE_ID_{id}: {name}
  </div>
);

const VehicleNode = ({ vehicle }: { vehicle: Vehicle }) => {
  const isEmergency = vehicle.type === "emergency";
  
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <motion.div
          layoutId={vehicle.id}
          initial={{ opacity: 0, scale: 0.8 }}
          animate={{ opacity: 1, scale: 1 }}
          exit={{ opacity: 0, scale: 0.5 }}
          className={cn(
            "relative w-10 h-10 md:w-12 md:h-12 rounded-lg flex items-center justify-center shadow-lg transition-colors border-2",
            isEmergency 
              ? "bg-red-950/80 border-red-500 text-red-500 animate-pulse shadow-red-500/20" 
              : "bg-slate-900/90 border-blue-500/50 text-blue-400 shadow-blue-500/10"
          )}
        >
          {isEmergency ? <AlertOctagon size={20} /> : <CarFront size={20} />}
          
          {/* PID Badge */}
          <div className="absolute -top-2 -right-2 bg-background border border-border text-[9px] px-1 rounded text-muted-foreground font-mono">
            PID:{vehicle.id.slice(0, 3)}
          </div>
        </motion.div>
      </TooltipTrigger>
      <TooltipContent className="font-mono text-xs border-border bg-black/90 text-foreground">
        <div className="space-y-1">
          <p className="font-bold border-b border-white/10 pb-1 mb-1">PCB (Process Block)</p>
          <div className="grid grid-cols-2 gap-x-4 gap-y-1">
            <span className="text-muted-foreground">PID:</span> <span>{vehicle.id}</span>
            <span className="text-muted-foreground">Type:</span> <span className={isEmergency ? "text-red-400" : "text-blue-400"}>{vehicle.type}</span>
            <span className="text-muted-foreground">Burst:</span> <span>{vehicle.burstTime}s</span>
            <span className="text-muted-foreground">Arrival:</span> <span>{vehicle.arrivalTime}s</span>
            <span className="text-muted-foreground">Wait:</span> <span>{vehicle.waitTime.toFixed(1)}s</span>
          </div>
        </div>
      </TooltipContent>
    </Tooltip>
  );
};

export function Visualizer({ state }: VisualizerProps) {
  const northRoad = state.roads.find(r => r.id === 0);
  const eastRoad = state.roads.find(r => r.id === 1);
  const southRoad = state.roads.find(r => r.id === 2);
  const westRoad = state.roads.find(r => r.id === 3);

  // Helper to render queue items
  const renderQueue = (road?: Road, direction: 'vertical' | 'horizontal' = 'vertical', reverse = false) => {
    if (!road) return null;
    const queue = [...road.queue]; // copy to sort/reverse if needed
    // Typically in visualizer, the head of queue is closest to intersection
    // So for North road (top), we want head at bottom.
    
    return (
      <div className={cn(
        "flex gap-2 items-center justify-end p-2 min-h-[60px] min-w-[60px]",
        direction === 'vertical' ? "flex-col h-full w-24 road-stripe" : "flex-row w-full h-24 road-stripe-horizontal",
        reverse && "flex-col-reverse flex-row-reverse" // For South/East to orient correctly
      )}>
        <AnimatePresence mode="popLayout">
          {queue.map((v) => (
            <VehicleNode key={v.id} vehicle={v} />
          ))}
        </AnimatePresence>
      </div>
    );
  };

  const getLightColor = (roadId: number) => {
    // If this is the active road
    if (state.activeRoadId === roadId) {
       // If almost done with quantum (arbitrary visual threshold, say < 20% left), show yellow?
       // For simplicity: Active = Green.
       return "bg-emerald-500 shadow-[0_0_20px_rgba(16,185,129,0.5)]";
    }
    return "bg-red-900/30 border border-red-500/20";
  };

  return (
    <div className="relative w-full aspect-square md:aspect-video max-w-4xl mx-auto bg-slate-950/50 rounded-2xl border border-white/5 overflow-hidden flex items-center justify-center p-8 md:p-12">
      {/* Background Grid Pattern */}
      <div className="absolute inset-0 bg-[linear-gradient(rgba(255,255,255,0.02)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,0.02)_1px,transparent_1px)] bg-[size:40px_40px] [mask-image:radial-gradient(ellipse_60%_60%_at_50%_50%,#000_70%,transparent_100%)] pointer-events-none" />

      <div className="relative w-full h-full max-w-2xl grid grid-cols-3 grid-rows-3 gap-4">
        
        {/* CORNERS (Decoration) */}
        <div className="border-r border-b border-white/5 rounded-br-3xl" />
        <div className="relative flex justify-center pb-4">
           {renderQueue(northRoad, 'vertical')}
           <div className="absolute top-2 -right-12 rotate-90"><RoadLabel name="NORTH" id={0} /></div>
        </div>
        <div className="border-l border-b border-white/5 rounded-bl-3xl" />

        {/* MIDDLE ROW */}
        <div className="relative flex items-center justify-end pr-4">
           {renderQueue(westRoad, 'horizontal')}
           <div className="absolute -top-6 left-2"><RoadLabel name="WEST" id={3} /></div>
        </div>
        
        {/* INTERSECTION / CPU */}
        <div className="relative z-10 bg-slate-900 rounded-2xl border-2 border-white/10 shadow-2xl flex flex-col items-center justify-center p-4">
          {/* Traffic Lights / CPU Cores */}
          <div className="absolute inset-0 grid grid-cols-2 grid-rows-2 p-3 gap-3">
             {/* North Light (Top) */}
             <div className={cn("rounded-full w-3 h-3 mx-auto transition-all duration-300", getLightColor(0))} />
             {/* East Light (Right) */}
             <div className={cn("rounded-full w-3 h-3 my-auto ml-auto transition-all duration-300", getLightColor(1))} />
             {/* West Light (Left) */}
             <div className={cn("rounded-full w-3 h-3 my-auto mr-auto transition-all duration-300", getLightColor(3))} />
             {/* South Light (Bottom) */}
             <div className={cn("rounded-full w-3 h-3 mx-auto mt-auto transition-all duration-300", getLightColor(2))} />
          </div>

          {/* Central CPU Status */}
          <div className="relative z-20 flex flex-col items-center gap-2">
            <div className={cn(
              "p-3 rounded-xl border transition-all duration-500",
              state.activeRoadId !== null 
                ? "bg-emerald-500/10 border-emerald-500/50 text-emerald-400 box-glow"
                : "bg-slate-800/50 border-white/10 text-muted-foreground"
            )}>
              <Cpu size={32} className={cn(state.activeRoadId !== null && "animate-pulse")} />
            </div>
            <div className="text-center">
              <div className="text-[10px] font-mono text-muted-foreground uppercase tracking-widest mb-1">CPU Status</div>
              <div className={cn(
                "text-xs font-bold font-mono px-2 py-0.5 rounded",
                 state.activeRoadId !== null ? "bg-emerald-500/20 text-emerald-300" : "bg-white/5 text-muted-foreground"
              )}>
                {state.activeRoadId !== null ? "EXECUTING" : "IDLE"}
              </div>
            </div>
          </div>

          {/* Context Switch Indicator (Yellow overlay) */}
          {state.activeRoadId === null && state.roads.some(r => r.queue.length > 0) && state.isRunning && (
            <div className="absolute inset-0 bg-amber-500/10 rounded-2xl border-2 border-amber-500/50 flex items-center justify-center animate-pulse z-30 backdrop-blur-[1px]">
               <div className="bg-black/80 px-3 py-1 rounded text-amber-500 font-mono text-xs font-bold flex gap-2 items-center border border-amber-500/30">
                 <Clock size={12} className="animate-spin" />
                 CONTEXT SWITCH
               </div>
            </div>
          )}

           {/* Interrupt Indicator */}
           {state.isEmergencyActive && (
             <div className="absolute -top-3 -right-3 z-40 bg-red-600 text-white text-[10px] font-bold px-2 py-1 rounded-full shadow-lg border border-red-400 animate-bounce flex gap-1 items-center">
               <Zap size={10} fill="currentColor" /> INTERRUPT
             </div>
           )}
        </div>

        <div className="relative flex items-center pl-4">
           {renderQueue(eastRoad, 'horizontal', true)}
           <div className="absolute -top-6 right-2"><RoadLabel name="EAST" id={1} /></div>
        </div>

        {/* BOTTOM ROW */}
        <div className="border-r border-t border-white/5 rounded-tr-3xl" />
        <div className="relative flex justify-center pt-4">
           {renderQueue(southRoad, 'vertical', true)}
           <div className="absolute bottom-2 -right-12 rotate-90"><RoadLabel name="SOUTH" id={2} /></div>
        </div>
        <div className="border-l border-t border-white/5 rounded-tl-3xl" />

      </div>
    </div>
  );
}
