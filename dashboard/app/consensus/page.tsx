// dashboard/app/consensus/page.tsx
import { VotingMatrix } from "@/components/consensus/voting-matrix";

export default function ConsensusPage() {
  return (
    <div className="space-y-6">
      <h1 className="text-xl font-bold">AI Consensus View</h1>
      <VotingMatrix />
    </div>
  );
}
