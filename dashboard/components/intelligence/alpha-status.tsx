// dashboard/components/intelligence/alpha-status.tsx
"use client";

interface AlphaStatusData {
  tier: string;
  sharpe: number;
  jensens_alpha: number;
  beta: number;
  portfolio_annual_pct: number;
  spy_annual_pct: number;
}

const TIER_CONFIG: Record<string, { label: string; color: string; bg: string; border: string }> = {
  learning:          { label: "Learning",          color: "text-warning",    bg: "bg-warning/10",    border: "border-warning/20" },
  alpha_achieved:    { label: "Alpha Achieved",    color: "text-accent",     bg: "bg-accent/10",     border: "border-accent/20" },
  exceptional_alpha: { label: "Exceptional Alpha", color: "text-purple-400", bg: "bg-purple-400/10", border: "border-purple-400/20" },
};

export function AlphaStatus({ data }: { data: AlphaStatusData | null }) {
  if (!data) return <div className="bg-surface border border-border rounded-xl p-5 h-32 animate-pulse" />;
  const tier = TIER_CONFIG[data.tier] || TIER_CONFIG.learning;

  return (
    <div className={`border rounded-xl p-5 ${tier.bg} ${tier.border}`}>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-sm font-semibold text-muted uppercase tracking-widest">Alpha Status</h2>
        <span className={`text-sm font-bold px-3 py-1 rounded-full ${tier.bg} ${tier.color} border ${tier.border}`}>
          {tier.label}
        </span>
      </div>
      <div className="grid grid-cols-4 gap-4">
        {[
          { label: "Sharpe (30d)", value: data.sharpe.toFixed(2), threshold: "≥1.5" },
          { label: "Jensen's α", value: `${data.jensens_alpha.toFixed(2)}%`, threshold: "≥2%" },
          { label: "Beta", value: data.beta.toFixed(2), threshold: "" },
          { label: "Excess vs SPY", value: `${(data.portfolio_annual_pct - data.spy_annual_pct).toFixed(1)}%`, threshold: "" },
        ].map(({ label, value, threshold }) => (
          <div key={label} className="text-center">
            <p className="text-xs text-muted mb-1">{label} {threshold && <span className="opacity-60">({threshold})</span>}</p>
            <p className={`text-xl font-bold font-mono ${tier.color}`}>{value}</p>
          </div>
        ))}
      </div>
      <div className="mt-4 space-y-2">
        <div className="flex justify-between text-xs text-muted">
          <span>Sharpe progress</span><span>{data.sharpe.toFixed(2)} / 1.5</span>
        </div>
        <div className="bg-border rounded-full h-1.5">
          <div className="h-1.5 rounded-full bg-accent transition-all"
               style={{ width: `${Math.min(100, (data.sharpe / 1.5) * 100)}%` }} />
        </div>
        <div className="flex justify-between text-xs text-muted">
          <span>Jensen's α progress</span><span>{data.jensens_alpha.toFixed(2)}% / 2%</span>
        </div>
        <div className="bg-border rounded-full h-1.5">
          <div className="h-1.5 rounded-full bg-accent transition-all"
               style={{ width: `${Math.min(100, (data.jensens_alpha / 2) * 100)}%` }} />
        </div>
      </div>
    </div>
  );
}
