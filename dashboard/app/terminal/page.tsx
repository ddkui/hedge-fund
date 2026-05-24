// dashboard/app/terminal/page.tsx
import { PriceChart } from "@/components/terminal/price-chart";
import { NewsFeed } from "@/components/terminal/news-feed";

export default function TerminalPage() {
  return (
    <div className="space-y-6">
      <h1 className="text-xl font-bold">Market Terminal</h1>
      <PriceChart />
      <NewsFeed />
    </div>
  );
}
