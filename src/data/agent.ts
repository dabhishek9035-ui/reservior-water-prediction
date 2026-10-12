/**
 * Agent API client – talks to the dam-agent backend (SSE streaming).
 * Integrates docs, data, and the AI agent so the chat can answer
 * questions about reservoirs, forecasts, model performance, etc.
 */
import type { Horizon } from './types';
import { AGENT_BASE_URL } from '@/config';

const AGENT_BASE = AGENT_BASE_URL.replace(/\/$/, '');

export type PageContext = {
  page?: 'home' | 'dams' | 'predictions';
  dam_id?: string;
  horizon?: Horizon;
  as_of?: string;
  window_days?: number;
  show_predicted?: boolean;
};

export type UIAction =
  | { type: 'select_dam'; dam_id: string }
  | { type: 'set_horizon'; value: number }
  | { type: 'set_as_of'; value: string }
  | { type: 'navigate'; to: string };

export type ChatSource = { id: string; label: string; detail?: string };

export type ChatMeta = {
  intent: string;
  tools: string[];
  ui_actions: UIAction[];
};

export type ChatDone = {
  answer: string;
  intent: string;
  tools: string[];
  sources: ChatSource[];
  warnings: string[];
  ui_actions: UIAction[];
  latency_ms: number;
  footer?: string;
};

export type StreamCallbacks = {
  onToken: (token: string) => void;
  onMeta?: (meta: ChatMeta) => void;
  onDone?: (done: ChatDone) => void;
  onError?: (error: Error) => void;
};

/**
 * Send a message to the agent with streaming SSE.
 * Calls onToken for each token, onMeta for planning info, and onDone with the full result.
 */
export async function askAgent(
  message: string,
  pageContext: PageContext,
  callbacks: StreamCallbacks,
  sessionId = 'web',
): Promise<{ meta?: ChatMeta; done?: ChatDone }> {
  let meta: ChatMeta | undefined;
  let done: ChatDone | undefined;

  try {
    const res = await fetch(`${AGENT_BASE}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        session_id: sessionId,
        message,
        page_context: pageContext,
        stream: true,
      }),
    });

    if (!res.ok) {
      throw new Error(`Agent returned ${res.status}: ${res.statusText}`);
    }

    const reader = res.body!.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    for (;;) {
      const { value, done: end } = await reader.read();
      if (end) break;
      buffer += decoder.decode(value, { stream: true });

      let idx: number;
      while ((idx = buffer.indexOf('\n\n')) >= 0) {
        const block = buffer.slice(0, idx);
        buffer = buffer.slice(idx + 2);

        const evMatch = /event:\s*(\w+)/.exec(block);
        const dataPrefixIdx = block.indexOf('data:');
        if (!evMatch || dataPrefixIdx === -1) continue;

        const ev = evMatch[1];
        const jsonText = block.slice(dataPrefixIdx + 5).trim();
        const data = JSON.parse(jsonText);

        if (ev === 'token') {
          callbacks.onToken(data.t);
        } else if (ev === 'meta') {
          meta = data;
          callbacks.onMeta?.(data);
        } else if (ev === 'done') {
          done = data;
          // Append any safety footer that wasn't streamed
          if (data.footer) callbacks.onToken('\n\n' + data.footer);
          callbacks.onDone?.(data);
        }
      }
    }
  } catch (err) {
    const error = err instanceof Error ? err : new Error(String(err));
    callbacks.onError?.(error);
  }

  return { meta, done };
}

export type AgentHealthInfo = {
  online: boolean;
  llmReachable: boolean;
  model?: string;
  mockData?: boolean;
};

/**
 * Check if the agent backend and LLM provider are reachable.
 */
export async function checkAgentHealth(): Promise<AgentHealthInfo> {
  try {
    const res = await fetch(`${AGENT_BASE}/health`, { signal: AbortSignal.timeout(3000) });
    if (!res.ok) return { online: false, llmReachable: false };
    const data = await res.json();
    return {
      online: !!data.ok,
      llmReachable: !!data.llm_reachable,
      model: data.model,
      mockData: data.mock_data,
    };
  } catch {
    return { online: false, llmReachable: false };
  }
}
