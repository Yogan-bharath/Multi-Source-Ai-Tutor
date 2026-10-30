'use client';
import React, { useState, useRef, useEffect } from 'react';
import {
  Send,
  Loader2,
  Bot,
  User,
  Sparkles,
  Plus,
  Copy,
  Check,
  ChevronDown,
  ChevronUp,
  ExternalLink,
  MessageSquare,
  Edit2,
  BookOpen,
  ArrowUp,
  Network,
  Search,
} from 'lucide-react';
import type {
  Message,
  ChatResponse,
  Project,
  Conversation,
} from '@/types';
import { AnswerCard } from './AnswerCard';
import { SourcePanel } from './SourcePanel';

interface ChatPanelProps {
  activeProject: Project | null;
  activeConversation: Conversation | null;
  conversations: Conversation[];
  onSelectConversation: (c: Conversation) => void;
  onNewChat: () => void;
  onConversationCreated?: (newConv: Conversation) => void;
  onConversationUpdated?: () => void;
  sourceCount: number;
}

/** Safely parse JSON from a fetch Response; falls back to text on failure. */
async function safeJson(resp: Response): Promise<any> {
  const text = await resp.text();
  try {
    return JSON.parse(text);
  } catch {
    throw new Error(
      `Server error (${resp.status}): ${text.slice(0, 200) || 'No response body'}`
    );
  }
}

function buildChatResponseFromMessage(msg: Message, projectId: string): ChatResponse | null {
  if (msg.role !== 'assistant') return null;
  if (!msg.classification && !msg.source_summaries) return null;

  return {
    answer: msg.content,
    classification: msg.classification || {
      classification: 'agree',
      confidence: 1.0,
      reasoning: 'Synthesized from project sources',
      key_differences: 'None',
    },
    source_summaries: msg.source_summaries || [],
    retrieved_chunks: msg.retrieved_chunks || {},
    session_id: projectId,
    question: '',
  };
}

export function ChatPanel({
  activeProject,
  activeConversation,
  conversations,
  onSelectConversation,
  onNewChat,
  onConversationCreated,
  onConversationUpdated,
  sourceCount,
}: ChatPanelProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [activeSourcesModalMsgId, setActiveSourcesModalMsgId] = useState<string | null>(null);
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [showHistoryMenu, setShowHistoryMenu] = useState(false);
  const [retrievalMode, setRetrievalMode] = useState<'vector' | 'hybrid'>('vector');
  const bottomRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Initialize retrieval mode from localStorage if available
  useEffect(() => {
    if (typeof window !== 'undefined') {
      const savedMode = localStorage.getItem('rag_retrieval_mode');
      if (savedMode === 'vector' || savedMode === 'hybrid') {
        setRetrievalMode(savedMode);
      }
    }
  }, []);

  // Load message history when active conversation changes
  useEffect(() => {
    if (!activeConversation) {
      setMessages([]);
      return;
    }

    const chatId = activeConversation.id || activeConversation._id;
    if (!chatId) return;

    let isMounted = true;
    setLoadingHistory(true);

    fetch(`/api/chats/${chatId}/messages`, {
      credentials: 'include',
    })
      .then((res) => {
        if (!res.ok) throw new Error('Failed to load chat history');
        return res.json();
      })
      .then((data) => {
        if (!isMounted) return;
        const rawMsgs = data.messages || [];
        const formatted: Message[] = rawMsgs.map((m: any) => ({
          id: m._id || m.id,
          role: m.role,
          content: m.content,
          classification: m.classification,
          source_summaries: m.source_summaries,
          retrieved_chunks: m.retrieved_chunks,
          retrieval_metadata: m.retrieval_metadata,
          chatResponse: buildChatResponseFromMessage(m, activeProject?.id || '') || undefined,
          timestamp: new Date(m.created_at),
        }));
        setMessages(formatted);
      })
      .catch((err) => {
        console.error('Error loading messages:', err);
      })
      .finally(() => {
        if (isMounted) setLoadingHistory(false);
      });

    return () => {
      isMounted = false;
    };
  }, [activeConversation, activeProject?.id]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading]);

  const handleCopyMessage = (msgId: string, text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedId(msgId);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  const sendMessage = async (overrideText?: string) => {
    const textToSend = (overrideText || input).trim();
    if (!textToSend || !activeProject || loading) return;
    setInput('');
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }

    let currentChatId = activeConversation?.id || activeConversation?._id;

    // Optimistic user message
    const tempUserMsgId = crypto.randomUUID();
    const optimisticUserMsg: Message = {
      id: tempUserMsgId,
      role: 'user',
      content: textToSend,
      timestamp: new Date(),
    };
    setMessages((prev) => [...prev, optimisticUserMsg]);
    setLoading(true);

    try {
      // 1. If no conversation active, create one under activeProject first
      if (!currentChatId) {
        const createConvResp = await fetch(`/api/projects/${activeProject.id || activeProject._id}/chats`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          credentials: 'include',
          body: JSON.stringify({
            title: textToSend.slice(0, 45) + (textToSend.length > 45 ? '...' : ''),
          }),
        });
        if (!createConvResp.ok) {
          const err = await safeJson(createConvResp);
          throw new Error(err.detail || 'Failed to create new conversation');
        }
        const newConv: Conversation = await createConvResp.json();
        currentChatId = newConv.id || newConv._id;
        onConversationCreated?.(newConv);
      }

      // 2. Post question to conversation
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 180_000);

      let resp: Response;
      try {
        resp = await fetch(`/api/chats/${currentChatId}/message`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          credentials: 'include',
          body: JSON.stringify({ question: textToSend, retrieval_mode: retrievalMode }),
          signal: controller.signal,
        });
      } finally {
        clearTimeout(timeout);
      }

      if (!resp.ok) {
        const errData = await safeJson(resp);
        throw new Error(
          typeof errData === 'object'
            ? errData.detail || errData.message || JSON.stringify(errData)
            : String(errData)
        );
      }

      const data = await safeJson(resp);
      const assistantRaw = data.assistant_message;
      const userRaw = data.user_message;

      const chatResp: ChatResponse = {
        answer: assistantRaw.content,
        classification: assistantRaw.classification || {
          classification: 'agree',
          confidence: 1.0,
          reasoning: 'Synthesized from project sources',
          key_differences: 'None',
        },
        source_summaries: assistantRaw.source_summaries || [],
        retrieved_chunks: assistantRaw.retrieved_chunks || {},
        session_id: activeProject.index_id,
        question: textToSend,
      };

      onConversationUpdated?.();

      const assistantMsg: Message = {
        id: assistantRaw.id || assistantRaw._id,
        role: 'assistant',
        content: assistantRaw.content,
        chatResponse: chatResp,
        classification: assistantRaw.classification,
        source_summaries: assistantRaw.source_summaries,
        retrieved_chunks: assistantRaw.retrieved_chunks,
        retrieval_metadata: assistantRaw.retrieval_metadata,
        timestamp: new Date(assistantRaw.created_at),
      };

      setMessages((prev) => {
        const updated = prev.filter((m) => m.id !== tempUserMsgId);
        return [
          ...updated,
          {
            id: userRaw.id || userRaw._id,
            role: 'user',
            content: userRaw.content,
            timestamp: new Date(userRaw.created_at),
          },
          assistantMsg,
        ];
      });
    } catch (e: any) {
      const errText =
        e.name === 'AbortError'
          ? 'Request timed out. The LLM may be slow — please try again.'
          : e.message || 'Unknown error occurred';

      setMessages((prev) => [
        ...prev,
        {
          id: crypto.randomUUID(),
          role: 'assistant',
          content: `⚠️ ${errText}`,
          timestamp: new Date(),
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex-1 flex flex-col h-full min-w-0 overflow-hidden relative" style={{ background: 'var(--canvas)' }}>
      {/* Workspace Header */}
      <div
        className="h-11 px-5 flex items-center justify-between flex-shrink-0"
        style={{ borderBottom: '1px solid var(--border)' }}
      >
        <div className="flex items-center gap-3 truncate mr-3">
          <div className="relative">
            <button
              onClick={() => setShowHistoryMenu(!showHistoryMenu)}
              className="flex items-center gap-1.5 text-[13px] font-medium px-2 py-1 rounded-md transition-colors duration-150 truncate max-w-sm"
              style={{ color: 'var(--ink)' }}
            >
              <MessageSquare className="w-3.5 h-3.5 flex-shrink-0" style={{ color: 'var(--ink-faint)' }} />
              <span className="truncate">
                {activeConversation?.title || 'New Discussion'}
              </span>
              <ChevronDown className="w-3 h-3 flex-shrink-0" style={{ color: 'var(--ink-faint)' }} />
            </button>

            {/* Conversation Switcher Dropdown */}
            {showHistoryMenu && (
              <div
                className="absolute left-0 top-full mt-1 w-64 rounded-lg shadow-modal py-1 z-40 max-h-60 overflow-y-auto animate-scaleIn"
                style={{ background: 'var(--surface-overlay)', border: '1px solid var(--border)' }}
              >
                <div className="px-3 py-1.5 text-[10px] font-semibold uppercase tracking-wider" style={{ color: 'var(--ink-faint)' }}>
                  Discussions
                </div>
                {conversations.length === 0 ? (
                  <p className="px-3 py-2 text-[13px]" style={{ color: 'var(--ink-faint)' }}>No discussions yet.</p>
                ) : (
                  conversations.map((c) => {
                    const cid = c.id || c._id;
                    const isSelected = activeConversation && (activeConversation.id === cid || activeConversation._id === cid);
                    return (
                      <button
                        key={cid}
                        onClick={() => {
                          onSelectConversation(c);
                          setShowHistoryMenu(false);
                        }}
                        className="w-full text-left px-3 py-1.5 text-[13px] truncate transition-colors duration-100 flex items-center"
                        style={{
                          background: isSelected ? 'var(--accent-muted)' : 'transparent',
                          color: isSelected ? 'var(--accent)' : 'var(--ink)',
                          fontWeight: isSelected ? 600 : 400,
                        }}
                      >
                        <span className="truncate">{c.title}</span>
                      </button>
                    );
                  })
                )}
              </div>
            )}
          </div>
        </div>

        <div className="flex items-center gap-2">
          {/* Retrieval Mode Selector */}
          <div
            className="flex items-center p-0.5 rounded-md text-[12px] font-medium"
            style={{ background: 'var(--canvas-alt)', border: '1px solid var(--border)' }}
            title="Choose retrieval method: Standard Vector RAG or Knowledge Graph-powered Hybrid RAG"
          >
            <button
              type="button"
              onClick={() => {
                setRetrievalMode('vector');
                if (typeof window !== 'undefined') localStorage.setItem('rag_retrieval_mode', 'vector');
              }}
              className="flex items-center gap-1.5 px-2.5 py-1 rounded transition-all duration-150"
              style={{
                background: retrievalMode === 'vector' ? 'var(--surface)' : 'transparent',
                color: retrievalMode === 'vector' ? 'var(--ink)' : 'var(--ink-faint)',
                boxShadow: retrievalMode === 'vector' ? '0 1px 2px rgba(0,0,0,0.05)' : 'none',
              }}
            >
              <Search className="w-3 h-3" />
              <span>Vector</span>
            </button>
            <button
              type="button"
              onClick={() => {
                setRetrievalMode('hybrid');
                if (typeof window !== 'undefined') localStorage.setItem('rag_retrieval_mode', 'hybrid');
              }}
              className="flex items-center gap-1.5 px-2.5 py-1 rounded transition-all duration-150"
              style={{
                background: retrievalMode === 'hybrid' ? 'var(--surface)' : 'transparent',
                color: retrievalMode === 'hybrid' ? 'var(--accent)' : 'var(--ink-faint)',
                boxShadow: retrievalMode === 'hybrid' ? '0 1px 2px rgba(0,0,0,0.05)' : 'none',
              }}
            >
              <Network className="w-3 h-3" />
              <span>Hybrid RAG</span>
            </button>
          </div>

          <button
            onClick={onNewChat}
            className="flex items-center gap-1.5 text-[13px] font-medium px-2.5 py-1.5 rounded-md transition-colors duration-150"
            style={{ color: 'var(--ink-muted)', border: '1px solid var(--border)' }}
          >
            <Plus className="w-3.5 h-3.5" />
            <span>New Chat</span>
          </button>
        </div>
      </div>

      {/* Messages Stream */}
      <div className="flex-1 overflow-y-auto px-4 sm:px-8 py-6 space-y-5">
        {loadingHistory ? (
          <div className="py-20 flex flex-col items-center justify-center text-center">
            <Loader2 className="w-6 h-6 animate-spin mb-2" style={{ color: 'var(--accent)' }} />
            <p className="text-[13px]" style={{ color: 'var(--ink-faint)' }}>Loading discussion history…</p>
          </div>
        ) : !activeProject ? (
          <div className="py-20 flex flex-col items-center justify-center text-center max-w-sm mx-auto">
            <div
              className="w-11 h-11 rounded-lg flex items-center justify-center mb-3"
              style={{ background: 'var(--canvas-alt)', border: '1px solid var(--border)' }}
            >
              <Sparkles className="w-5 h-5" style={{ color: 'var(--accent)' }} />
            </div>
            <h3 className="font-semibold text-sm" style={{ color: 'var(--ink)' }}>Select or Create a Notebook</h3>
            <p className="text-[13px] mt-1" style={{ color: 'var(--ink-faint)' }}>
              Choose a notebook from the top bar to load its sources and begin asking questions.
            </p>
          </div>
        ) : messages.length === 0 ? (
          /* Empty Discussion State */
          <div className="py-16 flex flex-col items-center justify-center text-center max-w-lg mx-auto">
            <div
              className="w-11 h-11 rounded-lg flex items-center justify-center mb-3"
              style={{ background: 'var(--accent-muted)', border: '1px solid var(--border)' }}
            >
              <BookOpen className="w-5 h-5" style={{ color: 'var(--accent)' }} />
            </div>
            <h3 className="font-semibold text-base" style={{ color: 'var(--ink)' }}>
              {activeProject.name}
            </h3>
            <p className="text-[13px] mt-1.5 max-w-md leading-relaxed" style={{ color: 'var(--ink-muted)' }}>
              {sourceCount > 0
                ? `Ready to assist across ${sourceCount} active source${sourceCount === 1 ? '' : 's'}. Ask questions, request comparisons, or synthesize takeaways.`
                : 'No sources added yet. Click "Add Sources" in the left sidebar to add websites, documents, or notes.'}
            </p>

            {sourceCount > 0 && (
              <div className="flex flex-wrap gap-2 justify-center mt-6 max-w-md">
                {[
                  'Explain the main concept in simple terms',
                  'Where do the sources agree or disagree?',
                  'Summarize the core methodology',
                  'What are the key limitations?',
                ].map((prompt, idx) => (
                  <button
                    key={idx}
                    onClick={() => sendMessage(prompt)}
                    className="px-3 py-1.5 text-[12px] rounded-md transition-colors duration-150 text-left"
                    style={{
                      background: 'var(--surface)',
                      color: 'var(--ink-muted)',
                      border: '1px solid var(--border)',
                    }}
                  >
                    {prompt}
                  </button>
                ))}
              </div>
            )}
          </div>
        ) : (
          messages.map((msg) => {
            const isUser = msg.role === 'user';
            const isSourcesExpanded = activeSourcesModalMsgId === msg.id;

            return (
              <div
                key={msg.id}
                className={`flex gap-3 max-w-3xl mx-auto ${isUser ? 'justify-end' : 'justify-start'}`}
              >
                {!isUser && (
                  <div
                    className="w-7 h-7 rounded-md flex items-center justify-center flex-shrink-0 mt-0.5"
                    style={{ background: 'var(--accent-muted)' }}
                  >
                    <Bot className="w-4 h-4" style={{ color: 'var(--accent)' }} />
                  </div>
                )}

                <div
                  className={`relative rounded-lg text-[13px] leading-relaxed transition-all ${
                    isUser
                      ? 'px-4 py-2.5 max-w-[85%] sm:max-w-[75%] font-normal whitespace-pre-wrap'
                      : 'px-4 py-3.5 flex-1 max-w-full'
                  }`}
                  style={
                    isUser
                      ? { background: 'var(--accent)', color: 'var(--accent-ink)' }
                      : { background: 'var(--surface)', border: '1px solid var(--border)', color: 'var(--ink)' }
                  }
                >
                  {isUser ? (
                    msg.content
                  ) : (
                    <div>
                      <AnswerCard answer={msg.content} />

                      {/* Footer Actions */}
                      <div
                        className="mt-3 pt-2.5 flex flex-wrap items-center justify-between gap-2 text-[11px]"
                        style={{ borderTop: '1px solid var(--border)', color: 'var(--ink-faint)' }}
                      >
                        <div className="flex items-center gap-2">
                          {msg.classification && (
                            <span
                              className="px-2 py-0.5 rounded-md text-[10px] font-semibold capitalize"
                              style={{ background: 'var(--canvas-alt)', color: 'var(--ink-muted)' }}
                            >
                              {msg.classification.classification} ({Math.round((msg.classification.confidence || 1) * 100)}%)
                            </span>
                          )}
                          {msg.retrieval_metadata && (
                            <span
                              className="px-2 py-0.5 rounded-md text-[10px] font-medium flex items-center gap-1"
                              style={{ background: 'var(--canvas-alt)', color: 'var(--ink-muted)' }}
                              title={`Retrieved using ${msg.retrieval_metadata.retrieval_mode} mode (${msg.retrieval_metadata.vector_results_count} vector chunks, ${msg.retrieval_metadata.graph_results_count} graph chunks)`}
                            >
                              <Network className="w-2.5 h-2.5" style={{ color: 'var(--accent)' }} />
                              <span>
                                {msg.retrieval_metadata.retrieval_mode === 'hybrid' ? 'Hybrid Evidence' : 'Vector Evidence'}
                                {msg.retrieval_metadata.retrieval_mode === 'hybrid' && (
                                  <span className="opacity-75 font-mono ml-0.5">
                                    (V:{msg.retrieval_metadata.vector_results_count} · G:{msg.retrieval_metadata.graph_results_count})
                                  </span>
                                )}
                              </span>
                            </span>
                          )}
                          {msg.chatResponse && (
                            <button
                              onClick={() =>
                                setActiveSourcesModalMsgId(isSourcesExpanded ? null : msg.id)
                              }
                              className="flex items-center gap-1 font-medium transition-colors duration-150"
                              style={{ color: 'var(--accent)' }}
                            >
                              <span>
                                {isSourcesExpanded ? 'Hide' : 'View'} Citations
                              </span>
                              {isSourcesExpanded ? (
                                <ChevronUp className="w-3 h-3" />
                              ) : (
                                <ChevronDown className="w-3 h-3" />
                              )}
                            </button>
                          )}
                        </div>

                        <div className="flex items-center gap-2">
                          <button
                            onClick={() => handleCopyMessage(msg.id, msg.content)}
                            className="p-1 rounded transition-colors duration-150 flex items-center gap-1"
                            style={{ color: 'var(--ink-faint)' }}
                            title="Copy answer"
                          >
                            {copiedId === msg.id ? (
                              <>
                                <Check className="w-3 h-3" style={{ color: 'var(--positive)' }} />
                                <span style={{ color: 'var(--positive)' }}>Copied</span>
                              </>
                            ) : (
                              <>
                                <Copy className="w-3 h-3" />
                                <span>Copy</span>
                              </>
                            )}
                          </button>
                        </div>
                      </div>

                      {/* Expandable Source Panel */}
                      {isSourcesExpanded && msg.chatResponse && (
                        <div className="mt-3 pt-3" style={{ borderTop: '1px solid var(--border)' }}>
                          <SourcePanel chatResponse={msg.chatResponse} />
                        </div>
                      )}
                    </div>
                  )}
                </div>

                {isUser && (
                  <div
                    className="w-7 h-7 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5 text-white text-xs font-semibold"
                    style={{ background: 'var(--accent)' }}
                  >
                    <User className="w-3.5 h-3.5" />
                  </div>
                )}
              </div>
            );
          })
        )}

        {loading && (
          <div className="flex gap-3 max-w-3xl mx-auto">
            <div
              className="w-7 h-7 rounded-md flex items-center justify-center flex-shrink-0 mt-0.5"
              style={{ background: 'var(--accent-muted)' }}
            >
              <Bot className="w-4 h-4" style={{ color: 'var(--accent)' }} />
            </div>
            <div
              className="rounded-lg px-4 py-3 text-[13px] flex items-center gap-2.5"
              style={{ background: 'var(--surface)', border: '1px solid var(--border)', color: 'var(--ink-muted)' }}
            >
              <Loader2 className="w-4 h-4 animate-spin" style={{ color: 'var(--accent)' }} />
              <span>Retrieving sources → Classifying → Synthesizing…</span>
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Question Composer */}
      <div className="p-4 flex-shrink-0" style={{ borderTop: '1px solid var(--border)' }}>
        <div className="max-w-3xl mx-auto">
          <div
            className="relative rounded-lg overflow-hidden transition-all"
            style={{ background: 'var(--surface)', border: '1px solid var(--border)' }}
          >
            <textarea
              ref={textareaRef}
              rows={1}
              value={input}
              onChange={(e) => {
                setInput(e.target.value);
                e.target.style.height = 'auto';
                e.target.style.height = `${Math.min(e.target.scrollHeight, 140)}px`;
              }}
              onKeyDown={handleKeyDown}
              disabled={!activeProject || loading}
              placeholder={
                !activeProject
                  ? 'Select a notebook to start…'
                  : 'Ask a question across your sources…'
              }
              className="w-full bg-transparent px-4 py-3 text-[13px] focus:outline-none resize-none max-h-36"
              style={{ color: 'var(--ink)' }}
            />

            <div
              className="flex items-center justify-between px-3.5 py-2 text-[11px]"
              style={{ borderTop: '1px solid var(--border-muted)', color: 'var(--ink-faint)' }}
            >
              <div className="flex items-center gap-1.5">
                <div className="w-1.5 h-1.5 rounded-full" style={{ background: sourceCount > 0 ? 'var(--positive)' : 'var(--border)' }} />
                <span>
                  {sourceCount} source{sourceCount === 1 ? '' : 's'} active
                </span>
              </div>

              <button
                onClick={() => sendMessage()}
                disabled={!activeProject || loading || !input.trim()}
                className="px-3 py-1.5 font-medium text-[12px] rounded-md transition-colors duration-150 flex items-center gap-1.5 disabled:opacity-40"
                style={{ background: 'var(--accent)', color: 'var(--accent-ink)' }}
              >
                <span>Send</span>
                <ArrowUp className="w-3 h-3" />
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
