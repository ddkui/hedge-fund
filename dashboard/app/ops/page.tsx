// dashboard/app/ops/page.tsx
import { AgentBoard } from "@/components/ops/agent-board";

export default function OpsPage() {
  return (
    <div className="space-y-6">
      <h1 className="text-xl font-bold">Operations</h1>
      <AgentBoard />
    </div>
  );
}
