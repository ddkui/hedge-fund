// dashboard/components/analytics/monthly-heatmap.tsx
"use client";

interface MonthlyReturn { year: number; month: number; return_pct: number; }

const MONTHS = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];

function cellColor(ret: number): string {
  if (ret > 5) return "bg-accent text-black";
  if (ret > 2) return "bg-accent/60 text-black";
  if (ret > 0) return "bg-accent/30 text-accent";
  if (ret === 0) return "bg-border text-muted";
  if (ret > -2) return "bg-danger/30 text-danger";
  if (ret > -5) return "bg-danger/60 text-white";
  return "bg-danger text-white";
}

export function MonthlyHeatmap({ data }: { data: MonthlyReturn[] }) {
  const years = [...new Set(data.map((d) => d.year))].sort();
  const lookup = new Map(data.map((d) => [`${d.year}-${d.month}`, d.return_pct]));

  return (
    <div className="bg-surface border border-border rounded-xl p-5">
      <h2 className="text-sm font-semibold text-muted uppercase tracking-widest mb-4">Monthly Returns</h2>
      <div className="overflow-x-auto">
        <table className="text-xs w-full">
          <thead>
            <tr>
              <th className="text-muted text-left pr-3 py-1 w-12">Year</th>
              {MONTHS.map((m) => (
                <th key={m} className="text-muted text-center px-1 py-1 w-14">{m}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {years.map((year) => (
              <tr key={year}>
                <td className="text-muted pr-3 py-1 font-mono">{year}</td>
                {Array.from({ length: 12 }, (_, i) => i + 1).map((month) => {
                  const ret = lookup.get(`${year}-${month}`);
                  return (
                    <td key={month} className="px-0.5 py-0.5">
                      {ret !== undefined ? (
                        <div
                          title={`${ret >= 0 ? "+" : ""}${ret.toFixed(2)}%`}
                          className={`text-center rounded px-1 py-1 font-mono cursor-help ${cellColor(ret)}`}
                        >
                          {ret >= 0 ? "+" : ""}{ret.toFixed(1)}
                        </div>
                      ) : (
                        <div className="text-center text-border px-1 py-1">—</div>
                      )}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
