// dashboard/app/activity/page.tsx
import { ActivityFeed } from "@/components/activity/activity-feed";

export default function ActivityPage() {
  return (
    <div className="space-y-6">
      <h1 className="text-xl font-bold">AI Activity</h1>
      <ActivityFeed />
    </div>
  );
}
