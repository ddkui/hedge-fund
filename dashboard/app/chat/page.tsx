// dashboard/app/chat/page.tsx
import { CioChat } from "@/components/chat/cio-chat";

export default function ChatPage() {
  return (
    <div className="space-y-4">
      <h1 className="text-xl font-bold">CIO Chat</h1>
      <CioChat />
    </div>
  );
}
