import { motion } from "framer-motion";
import { LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";

interface MetricCardProps {
  label: string;
  value: string | number;
  icon: LucideIcon;
  color?: "blue" | "green" | "yellow" | "red";
  subtext?: string;
}

export function MetricCard({ label, value, icon: Icon, color = "blue", subtext }: MetricCardProps) {
  const colors = {
    blue: "text-blue-400 bg-blue-500/10 border-blue-500/20",
    green: "text-emerald-400 bg-emerald-500/10 border-emerald-500/20",
    yellow: "text-amber-400 bg-amber-500/10 border-amber-500/20",
    red: "text-red-400 bg-red-500/10 border-red-500/20",
  };

  return (
    <motion.div 
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className={cn(
        "p-4 rounded-xl border backdrop-blur-sm transition-colors",
        colors[color]
      )}
    >
      <div className="flex items-center gap-3 mb-2">
        <div className={cn("p-2 rounded-lg bg-background/50", colors[color].split(" ")[0])}>
          <Icon size={18} />
        </div>
        <span className="text-sm font-medium text-muted-foreground uppercase tracking-wider font-mono">
          {label}
        </span>
      </div>
      <div className="flex items-end justify-between">
        <span className="text-2xl font-bold font-mono tracking-tight text-foreground/90">
          {value}
        </span>
        {subtext && (
          <span className="text-xs text-muted-foreground font-mono mb-1">
            {subtext}
          </span>
        )}
      </div>
    </motion.div>
  );
}
