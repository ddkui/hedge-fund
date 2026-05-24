// dashboard/components/terminal/news-feed.tsx
"use client";
import { useEffect, useState } from "react";
import { useWebSocket } from "@/lib/use-ws";

interface NewsItem {
  headline: string;
  source: string;
  time: string;
  sentiment_score: number | null;
}

export function NewsFeed() {
  const { messages } = useWebSocket();
  const [news, setNews] = useState<NewsItem[]>([]);

  useEffect(() => {
    const newsMsg = messages.find((m) => m.channel === "data.news");
    if (newsMsg?.data) {
      setNews((prev) => [newsMsg.data as unknown as NewsItem, ...prev].slice(0, 50));
    }
  }, [messages]);

  return (
    <div className="bg-surface border border-border rounded-xl p-5 h-[400px] overflow-y-auto">
      <h2 className="text-sm font-semibold mb-3 text-muted uppercase tracking-widest sticky top-0 bg-surface pb-2">Live News</h2>
      {news.length === 0 ? (
        <p className="text-muted text-sm">Waiting for news feed… start agents to populate.</p>
      ) : (
        <div className="space-y-3">
          {news.map((item, i) => (
            <div key={i} className="border-b border-border/50 pb-3">
              <p className="text-sm leading-snug">{item.headline}</p>
              <div className="flex items-center gap-2 mt-1">
                <span className="text-xs text-muted">{item.source}</span>
                {item.sentiment_score !== null && (
                  <span className={`text-xs px-1.5 py-0.5 rounded ${item.sentiment_score > 0.5 ? "text-accent bg-accent/10" : item.sentiment_score < -0.5 ? "text-danger bg-danger/10" : "text-muted bg-muted/10"}`}>
                    {item.sentiment_score > 0 ? "+" : ""}{(item.sentiment_score * 100).toFixed(0)}
                  </span>
                )}
                <span className="text-xs text-muted ml-auto">{new Date(item.time).toLocaleTimeString()}</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
