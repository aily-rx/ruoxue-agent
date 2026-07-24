/**
 * Root application component.
 *
 * Phase 1: chat-only layout.
 * Phase 3: adds Live2D canvas alongside chat.
 */

import { ChatPanel } from "./components/ChatPanel";

export default function App() {
  return (
    <div id="app">
      <ChatPanel />
    </div>
  );
}
