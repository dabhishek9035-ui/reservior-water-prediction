'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { usePathname, useRouter } from 'next/navigation';
import { MessageSquare, Send, X, Bot, User, AlertTriangle, ExternalLink, Sparkles, Loader2 } from 'lucide-react';
import { askAgent, checkAgentHealth } from '@/data/agent';
import type { AgentHealthInfo, ChatDone, ChatMeta, ChatSource, PageContext, UIAction } from '@/data/agent';
import { useAppStore } from '@/state/store';

/* ─── types ─── */
type Message = {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  sources?: ChatSource[];
  warnings?: string[];
  uiActions?: UIAction[];
  intent?: string;
  tools?: string[];
  latencyMs?: number;
  streaming?: boolean;
};

/* ─── suggested chips per page ─── */
const SUGGESTIONS: Record<string, string[]> = {
  home: [
    'Which reservoir is the fullest?',
    'Tell me about the data sources',
    'How does the forecast model work?',
    'Compare all reservoirs',
  ],
  dams: [
    'How full is Bhadra?',
    'Which regions are affected by Almatti overflow?',
    'Tell me about Tungabhadra dam',
    'Compare Kabini and KRS',
  ],
  predictions: [
    'What will the level be in 7 days?',
    'How accurate is this forecast?',
    'Show me the 30-day outlook',
    'What does persistence baseline mean?',
  ],
};

const AGENT_AVATAR = '/agent-avatar.png';

/* ─── CSS ─── */
const CHAT_CSS = `
.chat-fab{
  position:fixed;z-index:40;bottom:28px;right:28px;
  width:60px;height:60px;border-radius:50%;border:2px solid rgba(93,225,238,.35);
  background:rgba(3,14,19,.85);backdrop-filter:blur(14px);
  display:grid;place-items:center;cursor:pointer;
  box-shadow:0 8px 32px rgba(0,0,0,.5),0 0 0 0 rgba(93,225,238,.3);
  transition:transform .2s,box-shadow .25s;overflow:hidden;
}
.chat-fab:hover{transform:scale(1.08);box-shadow:0 8px 32px rgba(0,0,0,.5),0 0 0 8px rgba(93,225,238,.12)}
.chat-fab img{width:42px;height:42px;border-radius:50%;object-fit:cover}
.chat-fab .fab-badge{
  position:absolute;top:0;right:0;width:14px;height:14px;border-radius:50%;
  background:#5de1ee;border:2px solid #021419;
}

.chat-drawer{
  position:fixed;z-index:50;bottom:28px;right:28px;
  width:min(440px,calc(100vw - 40px));height:min(640px,calc(100vh - 56px));
  display:flex;flex-direction:column;
  background:rgba(3,12,17,.97);border:1px solid rgba(93,225,238,.2);
  border-radius:22px;overflow:hidden;
  box-shadow:0 32px 80px -20px rgba(0,0,0,.9),0 0 0 1px rgba(93,225,238,.08);
  backdrop-filter:blur(20px);animation:chat-in .25s ease-out;
}
@keyframes chat-in{from{opacity:0;transform:translateY(20px) scale(.96)}to{opacity:1;transform:translateY(0) scale(1)}}

.chat-header{
  display:flex;align-items:center;gap:12px;padding:16px 18px;
  border-bottom:1px solid rgba(93,225,238,.15);
  background:linear-gradient(180deg,rgba(6,24,32,.9),rgba(3,14,19,.95));
}
.chat-header-avatar{width:36px;height:36px;border-radius:50%;border:2px solid rgba(93,225,238,.3);object-fit:cover}
.chat-header-info{flex:1;display:flex;flex-direction:column;gap:2px}
.chat-header-info strong{font:600 14px var(--display,'Space Grotesk',sans-serif);color:#eefcfd;letter-spacing:-.01em}
.chat-header-info span{font:500 10px var(--mono,'DM Mono',monospace);letter-spacing:.1em;display:flex;align-items:center;gap:6px}
.chat-header-info .status-online{color:#6df0b0}
.chat-header-info .status-raw{color:#ffd166}
.chat-header-info .status-offline{color:#ff9aa1}
.chat-header-dot{width:6px;height:6px;border-radius:50%}
.chat-header-dot.online{background:#6df0b0;box-shadow:0 0 8px #6df0b0}
.chat-header-dot.raw{background:#ffd166;box-shadow:0 0 8px #ffd166}
.chat-header-dot.offline{background:#ff9aa1}
.chat-close{width:34px;height:34px;border-radius:10px;border:1px solid rgba(93,225,238,.15);
  background:transparent;color:#8aa1a8;cursor:pointer;display:grid;place-items:center;transition:.2s}
.chat-close:hover{border-color:rgba(93,225,238,.4);color:#eefcfd}

.chat-body{flex:1;overflow-y:auto;padding:16px;display:flex;flex-direction:column;gap:16px;
  scrollbar-width:thin;scrollbar-color:rgba(93,225,238,.2) transparent}

.chat-msg{display:flex;gap:10px;align-items:flex-start;animation:msg-in .2s ease-out}
@keyframes msg-in{from{opacity:0;transform:translateY(8px)}}
.chat-msg.user{flex-direction:row-reverse}
.chat-msg-avatar{width:30px;height:30px;border-radius:50%;flex:none;display:grid;place-items:center;
  border:1px solid rgba(93,225,238,.2);overflow:hidden}
.chat-msg-avatar img{width:100%;height:100%;object-fit:cover}
.chat-msg-avatar.user-avatar{background:rgba(93,225,238,.12);color:#5de1ee}
.chat-msg-bubble{max-width:82%;padding:12px 15px;border-radius:16px;font-size:13px;line-height:1.65;
  word-break:break-word;white-space:pre-wrap}
.chat-msg.user .chat-msg-bubble{
  background:linear-gradient(135deg,rgba(93,225,238,.18),rgba(93,225,238,.08));
  border:1px solid rgba(93,225,238,.25);color:#eefcfd;border-bottom-right-radius:4px;
}
.chat-msg.assistant .chat-msg-bubble{
  background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.08);
  color:#d0e4e6;border-bottom-left-radius:4px;
}

.chat-sources{display:flex;flex-wrap:wrap;gap:5px;margin-top:8px}
.chat-source-chip{display:inline-flex;align-items:center;gap:4px;padding:3px 9px;border-radius:999px;
  font:500 10px var(--mono);letter-spacing:.05em;color:#5de1ee;
  background:rgba(93,225,238,.08);border:1px solid rgba(93,225,238,.18)}
.chat-warning{display:flex;align-items:center;gap:6px;margin-top:6px;padding:6px 10px;border-radius:10px;
  font-size:11px;color:#ffb3b8;background:rgba(255,120,130,.08);border:1px solid rgba(255,120,130,.15)}
.chat-actions{display:flex;flex-wrap:wrap;gap:6px;margin-top:8px}
.chat-action-btn{display:inline-flex;align-items:center;gap:5px;padding:6px 12px;border-radius:10px;
  font-size:11px;font-weight:500;color:#5de1ee;background:rgba(93,225,238,.08);
  border:1px solid rgba(93,225,238,.2);cursor:pointer;transition:.2s}
.chat-action-btn:hover{background:rgba(93,225,238,.16);border-color:rgba(93,225,238,.4)}

.chat-latency{font:500 9px var(--mono);color:rgba(138,161,168,.5);margin-top:4px;text-align:right}

.chat-suggestions{padding:0 16px 12px;display:flex;flex-wrap:wrap;gap:6px}
.chat-suggestion{padding:7px 13px;border-radius:999px;font-size:12px;color:#8aa1a8;
  background:rgba(93,225,238,.05);border:1px solid rgba(93,225,238,.12);
  cursor:pointer;transition:.2s;white-space:nowrap}
.chat-suggestion:hover{color:#eefcfd;border-color:rgba(93,225,238,.35);background:rgba(93,225,238,.1)}

.chat-input-area{display:flex;align-items:center;gap:10px;padding:14px 16px;
  border-top:1px solid rgba(93,225,238,.12);background:rgba(3,14,19,.95)}
.chat-input{flex:1;min-width:0;padding:10px 14px;border-radius:12px;border:1px solid rgba(93,225,238,.15);
  background:rgba(2,10,14,.6);color:#eefcfd;font-size:14px;font-family:inherit;resize:none;
  outline:none;transition:border-color .2s;min-height:42px;max-height:120px;line-height:1.4}
.chat-input::placeholder{color:#5f747b}
.chat-input:focus{border-color:rgba(93,225,238,.45)}
.chat-send{width:42px;height:42px;border-radius:12px;border:none;
  background:linear-gradient(135deg,#5de1ee,#4bc8d5);color:#021419;
  cursor:pointer;display:grid;place-items:center;transition:.2s;flex:none}
.chat-send:hover{transform:scale(1.05);box-shadow:0 4px 16px rgba(93,225,238,.3)}
.chat-send:disabled{opacity:.4;cursor:not-allowed;transform:none;box-shadow:none}

.chat-typing{display:flex;align-items:center;gap:8px;padding:0 16px;font-size:12px;color:#8aa1a8}
.chat-typing-dots{display:flex;gap:3px}
.chat-typing-dots span{width:5px;height:5px;border-radius:50%;background:#5de1ee;
  animation:typing-bounce .8s infinite alternate}
.chat-typing-dots span:nth-child(2){animation-delay:.15s}
.chat-typing-dots span:nth-child(3){animation-delay:.3s}
@keyframes typing-bounce{from{opacity:.3;transform:translateY(0)}to{opacity:1;transform:translateY(-4px)}}

.chat-empty{flex:1;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:12px;
  padding:24px;text-align:center;color:#8aa1a8}
.chat-empty img{width:64px;height:64px;border-radius:50%;border:2px solid rgba(93,225,238,.2);object-fit:cover}
.chat-empty h3{font:600 16px var(--display);color:#eefcfd;margin:0;letter-spacing:-.01em}
.chat-empty p{font-size:12px;max-width:280px;margin:0;line-height:1.6}

@media(max-width:620px){
  .chat-fab{bottom:18px;right:18px;width:52px;height:52px}
  .chat-fab img{width:36px;height:36px}
  .chat-drawer{bottom:0;right:0;width:100vw;height:100vh;height:100dvh;border-radius:0}
}
`;

/* ─── component ─── */
export default function ChatDrawer() {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [streaming, setStreaming] = useState(false);
  const [health, setHealth] = useState<AgentHealthInfo | null>(null);

  const pathname = usePathname();
  const router = useRouter();

  const bodyRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const selectedDam = useAppStore((s) => s.selectedDam);
  const horizon = useAppStore((s) => s.horizon);
  const setSelectedDam = useAppStore((s) => s.setSelectedDam);
  const setHorizon = useAppStore((s) => s.setHorizon);

  // Detect the current page
  const page: 'home' | 'dams' | 'predictions' =
    pathname === '/predictions' ? 'predictions' : pathname === '/dams' ? 'dams' : 'home';

  // Build page context from current state
  const getPageContext = useCallback((): PageContext => {
    const params = typeof window !== 'undefined' ? new URLSearchParams(window.location.search) : undefined;
    return {
      page,
      dam_id: params?.get('dam') || selectedDam || undefined,
      horizon: (Number(params?.get('horizon')) || horizon || undefined) as PageContext['horizon'],
      as_of: params?.get('asOf') || undefined,
      show_predicted: undefined,
    };
  }, [page, selectedDam, horizon]);

  // Check agent health periodically so online/offline updates dynamically
  useEffect(() => {
    let active = true;
    const check = () => {
      checkAgentHealth().then((h) => {
        if (active) setHealth(h);
      });
    };
    check();
    const interval = setInterval(check, 3000);
    return () => {
      active = false;
      clearInterval(interval);
    };
  }, []);

  // Auto-scroll to bottom
  useEffect(() => {
    if (bodyRef.current) {
      bodyRef.current.scrollTop = bodyRef.current.scrollHeight;
    }
  }, [messages]);

  // Focus input when drawer opens
  useEffect(() => {
    if (open && inputRef.current) {
      setTimeout(() => inputRef.current?.focus(), 100);
    }
  }, [open]);

  // Send message
  const send = useCallback(async (text: string) => {
    if (!text.trim() || streaming) return;

    const userMsg: Message = {
      id: `u-${Date.now()}`,
      role: 'user',
      content: text.trim(),
    };

    const assistantId = `a-${Date.now()}`;
    const assistantMsg: Message = {
      id: assistantId,
      role: 'assistant',
      content: '',
      streaming: true,
    };

    setMessages((msgs) => [...msgs, userMsg, assistantMsg]);
    setInput('');
    setStreaming(true);

    const pageCtx = getPageContext();

    await askAgent(text.trim(), pageCtx, {
      onToken: (token) => {
        setMessages((msgs) =>
          msgs.map((m) =>
            m.id === assistantId ? { ...m, content: m.content + token } : m
          )
        );
      },
      onMeta: (meta) => {
        setMessages((msgs) =>
          msgs.map((m) =>
            m.id === assistantId
              ? { ...m, intent: meta.intent, tools: meta.tools, uiActions: meta.ui_actions }
              : m
          )
        );
      },
      onDone: (done) => {
        setMessages((msgs) =>
          msgs.map((m) =>
            m.id === assistantId
              ? {
                  ...m,
                  streaming: false,
                  sources: done.sources,
                  warnings: done.warnings,
                  uiActions: done.ui_actions,
                  latencyMs: done.latency_ms,
                }
              : m
          )
        );
      },
      onError: (error) => {
        setMessages((msgs) =>
          msgs.map((m) =>
            m.id === assistantId
              ? {
                  ...m,
                  content: m.content || `Sorry, I couldn't reach the assistant. ${error.message}`,
                  streaming: false,
                  warnings: ['agent_unreachable'],
                }
              : m
          )
        );
      },
    });

    setStreaming(false);
  }, [streaming, getPageContext]);

  // Handle UI actions from the agent
  const handleAction = useCallback((action: UIAction) => {
    switch (action.type) {
      case 'select_dam':
        setSelectedDam(action.dam_id);
        break;
      case 'set_horizon':
        setHorizon(action.value as 1 | 7 | 14 | 30);
        break;
      case 'navigate':
        router.push(action.to);
        break;
    }
  }, [setSelectedDam, setHorizon, router]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      send(input);
    }
  };

  const suggestions = SUGGESTIONS[page] ?? SUGGESTIONS.home;

  return (
    <>
      <style dangerouslySetInnerHTML={{ __html: CHAT_CSS }} />

      {/* FAB */}
      {!open && (
        <button
          className="chat-fab"
          onClick={() => setOpen(true)}
          aria-label="Open chat assistant"
        >
          <img src={AGENT_AVATAR} alt="Jala assistant" />
          {health?.online && (
            <span
              className="fab-badge"
              style={{ background: health.llmReachable ? '#5de1ee' : '#ffd166' }}
            />
          )}
        </button>
      )}

      {/* Drawer */}
      {open && (
        <div className="chat-drawer" role="dialog" aria-label="Chat assistant">
          {/* Header */}
          <div className="chat-header">
            <img className="chat-header-avatar" src={AGENT_AVATAR} alt="Jala" />
            <div className="chat-header-info">
              <strong>Jala Assistant</strong>
              <span className={health?.llmReachable ? 'status-online' : health?.online ? 'status-raw' : 'status-offline'}>
                <span className={`chat-header-dot ${health?.llmReachable ? 'online' : health?.online ? 'raw' : health ? 'offline' : ''}`} />
                {health === null
                  ? 'CONNECTING…'
                  : health.llmReachable
                  ? `ONLINE · ${health.model ?? 'QWEN 7B'}`
                  : health.online
                  ? 'RAW DATA MODE · OLLAMA CONNECTING'
                  : 'AGENT OFFLINE · RUN PORT 8100'}
              </span>
            </div>
            <button className="chat-close" onClick={() => setOpen(false)} aria-label="Close chat">
              <X size={16} />
            </button>
          </div>

          {/* Body */}
          <div className="chat-body" ref={bodyRef}>
            {messages.length === 0 && (
              <div className="chat-empty">
                <img src={AGENT_AVATAR} alt="" />
                <h3>Jala Assistant</h3>
                <p>
                  Ask me about Karnataka's reservoirs, water levels, forecasts,
                  the LSTM model, data sources, or affected regions.
                </p>
              </div>
            )}

            {messages.map((msg) => (
              <div key={msg.id} className={`chat-msg ${msg.role}`}>
                <div className={`chat-msg-avatar ${msg.role === 'user' ? 'user-avatar' : ''}`}>
                  {msg.role === 'user' ? (
                    <User size={15} />
                  ) : (
                    <img src={AGENT_AVATAR} alt="" />
                  )}
                </div>
                <div>
                  <div className="chat-msg-bubble">
                    {msg.content}
                    {msg.streaming && !msg.content && (
                      <span className="chat-typing-dots">
                        <span /><span /><span />
                      </span>
                    )}
                    {msg.streaming && msg.content && (
                      <span style={{ display: 'inline-block', width: 6, height: 14, background: '#5de1ee', borderRadius: 2, marginLeft: 2, animation: 'typing-bounce .5s infinite alternate' }} />
                    )}
                  </div>

                  {/* Sources */}
                  {msg.sources && msg.sources.length > 0 && (
                    <div className="chat-sources">
                      {msg.sources.map((s) => (
                        <span key={s.id} className="chat-source-chip" title={s.detail || s.label}>
                          [{s.id}] {s.label}
                        </span>
                      ))}
                    </div>
                  )}

                  {/* Warnings */}
                  {msg.warnings && msg.warnings.length > 0 && (
                    <>
                      {msg.warnings.includes('unverified_numbers') && (
                        <div className="chat-warning">
                          <AlertTriangle size={13} />
                          Some figures may need verification
                        </div>
                      )}
                      {msg.warnings.includes('llm_unavailable') && (
                        <div className="chat-warning">
                          <AlertTriangle size={13} />
                          Assistant offline — showing raw data
                        </div>
                      )}
                    </>
                  )}

                  {/* UI Actions */}
                  {msg.uiActions && msg.uiActions.length > 0 && !msg.streaming && (
                    <div className="chat-actions">
                      {msg.uiActions.map((action, i) => (
                        <button
                          key={i}
                          className="chat-action-btn"
                          onClick={() => handleAction(action)}
                        >
                          {action.type === 'navigate' ? (
                            <><ExternalLink size={12} /> Go to {action.to}</>
                          ) : action.type === 'select_dam' ? (
                            <><Sparkles size={12} /> Select {action.dam_id}</>
                          ) : action.type === 'set_horizon' ? (
                            <><Sparkles size={12} /> Set {action.value}-day horizon</>
                          ) : null}
                        </button>
                      ))}
                    </div>
                  )}

                  {/* Latency */}
                  {msg.latencyMs !== undefined && !msg.streaming && (
                    <div className="chat-latency">{msg.latencyMs}ms</div>
                  )}
                </div>
              </div>
            ))}
          </div>

          {/* Suggestions */}
          {messages.length === 0 && (
            <div className="chat-suggestions">
              {suggestions.map((s) => (
                <button
                  key={s}
                  className="chat-suggestion"
                  onClick={() => send(s)}
                  disabled={streaming}
                >
                  {s}
                </button>
              ))}
            </div>
          )}

          {/* Input */}
          <div className="chat-input-area">
            <textarea
              ref={inputRef}
              className="chat-input"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask about reservoirs, levels, forecasts…"
              rows={1}
              disabled={streaming}
            />
            <button
              className="chat-send"
              onClick={() => send(input)}
              disabled={streaming || !input.trim()}
              aria-label="Send message"
            >
              {streaming ? <Loader2 size={18} className="animate-spin" /> : <Send size={18} />}
            </button>
          </div>
        </div>
      )}
    </>
  );
}
