import { useEffect, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Terminal, Cpu, AlertTriangle, ArrowRightLeft } from "lucide-react";
import { ScrollArea } from "@/components/ui/scroll-area";

interface TerminalLogProps {
  logs: string[];
}

export function TerminalLog({ logs }: TerminalLogProps) {
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      const scrollElement = scrollRef.current.querySelector('[data-radix-scroll-area-viewport]');
      if (scrollElement) {
        scrollElement.scrollTop = scrollElement.scrollHeight;
      }
    }
  }, [logs]);

  const getLogIcon = (log: string) => {
    if (log.includes("Emergency") || log.includes("Interrupt")) return <AlertTriangle className="text-red-500" size={14} />;
    if (log.includes("Switch")) return <ArrowRightLeft className="text-amber-500" size={14} />;
    if (log.includes("Quantum")) return <Cpu className="text-blue-500" size={14} />;
    return <Terminal className="text-muted-foreground" size={14} />;
  };

  return (
    <div className="h-full flex flex-col bg-black/40 border border-border/50 rounded-xl overflow-hidden backdrop-blur-md">
      <div className="flex items-center justify-between px-4 py-3 border-b border-border/50 bg-muted/20">
        <div className="flex items-center gap-2">
          <Terminal size={16} className="text-muted-foreground" />
          <h3 className="text-sm font-semibold font-mono text-muted-foreground">KERNEL LOGS</h3>
        </div>
        <div className="flex gap-1.5">
          <div className="w-2.5 h-2.5 rounded-full bg-red-500/20 border border-red-500/50" />
          <div className="w-2.5 h-2.5 rounded-full bg-amber-500/20 border border-amber-500/50" />
          <div className="w-2.5 h-2.5 rounded-full bg-emerald-500/20 border border-emerald-500/50" />
        </div>
      </div>
      
      <ScrollArea ref={scrollRef} className="flex-1 p-4 font-mono text-xs md:text-sm">
        <div className="flex flex-col gap-2">
          <AnimatePresence initial={false}>
            {logs.length === 0 && (
              <div className="text-muted-foreground/40 italic">System idle... Waiting for processes...</div>
            )}
            {logs.map((log, i) => (
              <motion.div
                key={i}
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                className="flex items-start gap-3 text-muted-foreground hover:text-foreground transition-colors"
              >
                <span className="mt-0.5 shrink-0 opacity-70">
                  {getLogIcon(log)}
                </span>
                <span className="leading-relaxed">
                  <span className="text-primary/30 mr-2">[{new Date().toLocaleTimeString()}]</span>
                  {log}
                </span>
              </motion.div>
            ))}
          </AnimatePresence>
        </div>
      </ScrollArea>
    </div>
  );
}
