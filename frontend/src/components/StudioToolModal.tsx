'use client';
import React, { useState, useEffect } from 'react';
import {
  X,
  RotateCcw,
  Copy,
  Check,
  Loader2,
  AlertCircle,
  FileText,
  Layers,
  HelpCircle,
  Network,
  BookOpen,
  Table as TableIcon,
  ChevronLeft,
  ChevronRight,
  Sparkles,
} from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import type {
  StudioToolType,
  StudioQuizQuestion,
} from '@/types';
import { parseProvenanceTags } from './ProvenanceTag';

interface StudioToolModalProps {
  isOpen: boolean;
  onClose: () => void;
  toolType: StudioToolType | null;
  projectId: string;
  projectName?: string;
}

export function StudioToolModal({
  isOpen,
  onClose,
  toolType,
  projectId,
  projectName,
}: StudioToolModalProps) {
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  // Flashcards state
  const [currentCardIndex, setCurrentCardIndex] = useState(0);
  const [isFlipped, setIsFlipped] = useState(false);

  // Quiz state
  const [selectedAnswers, setSelectedAnswers] = useState<Record<number, number>>({});

  const fetchToolData = async (forceRefresh = false) => {
    if (!toolType || !projectId) return;
    setLoading(true);
    setError(null);
    try {
      const url = `/api/projects/${projectId}/studio/${toolType}${forceRefresh ? '?refresh=true' : ''}`;
      const res = await fetch(url, { credentials: 'include' });
      const json = await res.json();
      if (!res.ok) {
        throw new Error(json.detail || `Failed to generate ${toolType}`);
      }
      setData(json.data);
      setCurrentCardIndex(0);
      setIsFlipped(false);
      setSelectedAnswers({});
    } catch (e: any) {
      setError(e.message || 'Error generating studio tool content');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (isOpen && toolType && projectId) {
      fetchToolData(false);
    } else {
      setData(null);
      setError(null);
    }
  }, [isOpen, toolType, projectId]);

  if (!isOpen || !toolType) return null;

  const copyContent = () => {
    let textToCopy = '';
    if (toolType === 'summary') {
      textToCopy = `${data?.title || 'Summary'}\n\n${data?.overview || ''}\n\nKey Takeaways:\n${(data?.key_takeaways || []).join('\n')}`;
    } else if (toolType === 'notes') {
      textToCopy = data?.markdown_content || '';
    } else {
      textToCopy = JSON.stringify(data, null, 2);
    }
    navigator.clipboard.writeText(textToCopy);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const getToolTitle = () => {
    switch (toolType) {
      case 'summary':
        return 'Executive Overview';
      case 'notes':
        return 'Structured Study Notes';
      case 'flashcards':
        return 'Interactive Flashcards';
      case 'quiz':
        return 'Practice Assessment';
      case 'mindmap':
        return 'Hierarchical Mind Map';
      case 'datatable':
        return 'Comparative Data Matrix';
      default:
        return 'Studio Tool';
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 animate-fadeIn"
      style={{ background: 'rgba(0, 0, 0, 0.65)', backdropFilter: 'blur(4px)' }}
      onKeyDown={(e) => e.key === 'Escape' && onClose()}
    >
      <div
        className="rounded-2xl shadow-modal w-full max-w-3xl overflow-hidden flex flex-col max-h-[90vh] animate-scaleIn"
        style={{
          background: 'var(--surface-overlay)',
          border: '1px solid var(--border)',
          color: 'var(--ink)',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div
          className="p-4 flex items-center justify-between"
          style={{
            borderBottom: '1px solid var(--border)',
            background: 'var(--surface)',
          }}
        >
          <div className="flex items-center gap-2.5">
            <div
              className="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0"
              style={{
                background: 'var(--accent-muted)',
                color: 'var(--accent)',
                border: '1px solid var(--accent)',
              }}
            >
              <Sparkles className="w-4 h-4" />
            </div>
            <div>
              <h2 className="text-[14px] font-bold leading-tight" style={{ color: 'var(--ink)' }}>
                {getToolTitle()}
              </h2>
              <p className="text-[11px]" style={{ color: 'var(--ink-muted)' }}>
                Grounded in <span className="font-medium" style={{ color: 'var(--ink)' }}>{projectName || 'Project Sources'}</span>
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => fetchToolData(true)}
              disabled={loading}
              className="p-1.5 rounded-lg transition-colors flex items-center gap-1.5 text-[12px] px-2.5 hover:opacity-80"
              style={{
                background: 'var(--canvas-alt)',
                border: '1px solid var(--border)',
                color: 'var(--ink-muted)',
              }}
              title="Regenerate"
            >
              <RotateCcw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
              <span className="hidden sm:inline">Regenerate</span>
            </button>
            <button
              onClick={copyContent}
              disabled={loading || !data}
              className="p-1.5 rounded-lg transition-colors flex items-center gap-1.5 text-[12px] px-2.5 hover:opacity-80"
              style={{
                background: 'var(--canvas-alt)',
                border: '1px solid var(--border)',
                color: 'var(--ink-muted)',
              }}
              title="Copy content"
            >
              {copied ? (
                <>
                  <Check className="w-3.5 h-3.5" style={{ color: 'var(--positive)' }} />
                  <span className="hidden sm:inline" style={{ color: 'var(--positive)' }}>Copied</span>
                </>
              ) : (
                <>
                  <Copy className="w-3.5 h-3.5" />
                  <span className="hidden sm:inline">Copy</span>
                </>
              )}
            </button>
            <button
              onClick={onClose}
              className="p-1.5 rounded-lg transition-colors hover:opacity-80 ml-1"
              style={{ color: 'var(--ink-faint)' }}
              title="Close modal"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Content body */}
        <div className="flex-1 overflow-y-auto p-6 space-y-4">
          {loading ? (
            <div className="py-20 flex flex-col items-center justify-center text-center">
              <Loader2 className="w-8 h-8 animate-spin mb-3" style={{ color: 'var(--accent)' }} />
              <p className="text-[13px] font-semibold" style={{ color: 'var(--ink)' }}>
                Synthesizing {getToolTitle().toLowerCase()} with AI…
              </p>
              <p className="text-[11px] mt-1" style={{ color: 'var(--ink-muted)' }}>
                Analyzing and grounding facts across active project sources
              </p>
            </div>
          ) : error ? (
            <div
              className="p-4 rounded-xl text-[12px] flex items-start gap-3"
              style={{
                background: 'var(--negative-muted)',
                border: '1px solid var(--negative)',
                color: 'var(--negative)',
              }}
            >
              <AlertCircle className="w-5 h-5 flex-shrink-0 mt-0.5" />
              <div>
                <p className="font-semibold">Generation Failed</p>
                <p className="mt-1 opacity-90">{error}</p>
                <button
                  onClick={() => fetchToolData(true)}
                  className="mt-3 px-3 py-1.5 rounded-lg font-medium transition-opacity hover:opacity-90"
                  style={{
                    background: 'var(--negative)',
                    color: '#FFFFFF',
                  }}
                >
                  Retry Generation
                </button>
              </div>
            </div>
          ) : !data ? null : (
            <>
              {/* TOOL 1: SUMMARY */}
              {toolType === 'summary' && (
                <div className="space-y-5" style={{ color: 'var(--ink)' }}>
                  <div>
                    <h3 className="text-[17px] font-bold" style={{ color: 'var(--ink)' }}>
                      {data.title || 'Source Material Overview'}
                    </h3>
                    <p className="text-[13px] leading-relaxed mt-2 whitespace-pre-wrap" style={{ color: 'var(--ink)' }}>
                      {data.overview}
                    </p>
                  </div>

                  {data.key_takeaways?.length > 0 && (
                    <div
                      className="rounded-xl p-4"
                      style={{
                        background: 'var(--canvas-alt)',
                        border: '1px solid var(--border)',
                      }}
                    >
                      <h4
                        className="text-[11px] font-bold uppercase tracking-wider mb-3"
                        style={{ color: 'var(--accent)' }}
                      >
                        Key Takeaways
                      </h4>
                      <ul className="space-y-2 text-[12px]">
                        {data.key_takeaways.map((item: string, idx: number) => (
                          <li key={idx} className="flex items-start gap-2" style={{ color: 'var(--ink)' }}>
                            <span className="font-bold" style={{ color: 'var(--accent)' }}>•</span>
                            <span>{parseProvenanceTags(item)}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {data.source_breakdown?.length > 0 && (
                    <div
                      className="rounded-xl p-4"
                      style={{
                        background: 'var(--canvas-alt)',
                        border: '1px solid var(--border)',
                      }}
                    >
                      <h4
                        className="text-[11px] font-bold uppercase tracking-wider mb-2"
                        style={{ color: 'var(--ink-muted)' }}
                      >
                        Source Breakdown
                      </h4>
                      <div className="space-y-2 text-[12px]">
                        {data.source_breakdown.map((s: any, idx: number) => (
                          <div key={idx} className="flex gap-2" style={{ color: 'var(--ink)' }}>
                            <span className="font-semibold" style={{ color: 'var(--accent)' }}>
                              {s.source_id}:
                            </span>
                            <span>{s.main_contribution}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* TOOL 2: FLASHCARDS */}
              {toolType === 'flashcards' && (
                <div className="space-y-4">
                  {data.flashcards?.length > 0 ? (
                    <div className="max-w-lg mx-auto">
                      <div className="flex items-center justify-between text-[12px] mb-2" style={{ color: 'var(--ink-muted)' }}>
                        <span>
                          Card {currentCardIndex + 1} of {data.flashcards.length}
                        </span>
                        <span className="font-mono text-[11px]" style={{ color: 'var(--accent)' }}>
                          Click card to flip
                        </span>
                      </div>

                      {/* Flashcard Component */}
                      <div
                        onClick={() => setIsFlipped(!isFlipped)}
                        className="min-h-[220px] rounded-2xl p-6 cursor-pointer border transition-all duration-300 flex flex-col justify-between select-none shadow-sm"
                        style={{
                          background: isFlipped ? 'var(--canvas-alt)' : 'var(--surface)',
                          borderColor: isFlipped ? 'var(--accent)' : 'var(--border)',
                          color: 'var(--ink)',
                        }}
                      >
                        <div
                          className="flex items-center justify-between text-[11px] uppercase tracking-wider font-semibold"
                          style={{ color: 'var(--ink-muted)' }}
                        >
                          <span>{data.flashcards[currentCardIndex]?.category || 'Concept'}</span>
                          <span style={{ color: 'var(--accent)' }}>{isFlipped ? 'Answer' : 'Question'}</span>
                        </div>

                        <div className="my-auto text-center py-4">
                          <p className="text-[15px] font-medium leading-relaxed">
                            {isFlipped
                              ? parseProvenanceTags(data.flashcards[currentCardIndex]?.back || '')
                              : data.flashcards[currentCardIndex]?.front}
                          </p>
                        </div>

                        <div className="flex items-center justify-between text-[10px]" style={{ color: 'var(--ink-faint)' }}>
                          <span>{data.flashcards[currentCardIndex]?.source || ''}</span>
                          <span style={{ color: 'var(--accent)' }}>Flip ↻</span>
                        </div>
                      </div>

                      {/* Card navigation controls */}
                      <div className="flex items-center justify-center gap-4 mt-4">
                        <button
                          onClick={() => {
                            setCurrentCardIndex((prev) => Math.max(0, prev - 1));
                            setIsFlipped(false);
                          }}
                          disabled={currentCardIndex === 0}
                          className="p-2 rounded-xl transition-colors disabled:opacity-30 hover:opacity-80"
                          style={{
                            background: 'var(--canvas-alt)',
                            border: '1px solid var(--border)',
                            color: 'var(--ink)',
                          }}
                        >
                          <ChevronLeft className="w-4 h-4" />
                        </button>
                        <span className="text-[12px] font-mono" style={{ color: 'var(--ink-muted)' }}>
                          {currentCardIndex + 1} / {data.flashcards.length}
                        </span>
                        <button
                          onClick={() => {
                            setCurrentCardIndex((prev) =>
                              Math.min(data.flashcards.length - 1, prev + 1)
                            );
                            setIsFlipped(false);
                          }}
                          disabled={currentCardIndex === data.flashcards.length - 1}
                          className="p-2 rounded-xl transition-colors disabled:opacity-30 hover:opacity-80"
                          style={{
                            background: 'var(--canvas-alt)',
                            border: '1px solid var(--border)',
                            color: 'var(--ink)',
                          }}
                        >
                          <ChevronRight className="w-4 h-4" />
                        </button>
                      </div>
                    </div>
                  ) : (
                    <p className="text-[12px] text-center py-8" style={{ color: 'var(--ink-muted)' }}>
                      No flashcards generated.
                    </p>
                  )}
                </div>
              )}

              {/* TOOL 3: QUIZ */}
              {toolType === 'quiz' && (
                <div className="space-y-5">
                  {data.questions?.map((q: StudioQuizQuestion, qIdx: number) => {
                    const selected = selectedAnswers[qIdx];
                    const isAnswered = selected !== undefined;

                    return (
                      <div
                        key={q.id || qIdx}
                        className="p-4 rounded-xl space-y-3"
                        style={{
                          background: 'var(--canvas-alt)',
                          border: '1px solid var(--border)',
                        }}
                      >
                        <div className="flex items-start gap-2">
                          <span className="text-[13px] font-bold" style={{ color: 'var(--accent)' }}>
                            {qIdx + 1}.
                          </span>
                          <h4 className="text-[13px] font-semibold leading-snug" style={{ color: 'var(--ink)' }}>
                            {q.question}
                          </h4>
                        </div>

                        <div className="space-y-1.5 pl-4">
                          {q.options.map((opt, optIdx) => {
                            const isThisSelected = selected === optIdx;
                            const isCorrect = q.answer_index === optIdx;

                            let optBg = 'var(--surface)';
                            let optBorder = 'var(--border)';
                            let optColor = 'var(--ink)';

                            if (isAnswered) {
                              if (isCorrect) {
                                optBg = 'var(--positive-muted)';
                                optBorder = 'var(--positive)';
                                optColor = 'var(--positive)';
                              } else if (isThisSelected) {
                                optBg = 'var(--negative-muted)';
                                optBorder = 'var(--negative)';
                                optColor = 'var(--negative)';
                              }
                            }

                            return (
                              <button
                                key={optIdx}
                                onClick={() => {
                                  if (!isAnswered) {
                                    setSelectedAnswers((prev) => ({ ...prev, [qIdx]: optIdx }));
                                  }
                                }}
                                className="w-full text-left px-3 py-2 text-[12px] rounded-lg transition-colors flex items-center justify-between"
                                style={{
                                  background: optBg,
                                  border: `1px solid ${optBorder}`,
                                  color: optColor,
                                }}
                              >
                                <span>{opt}</span>
                                {isAnswered && isCorrect && (
                                  <Check className="w-3.5 h-3.5 flex-shrink-0" style={{ color: 'var(--positive)' }} />
                                )}
                              </button>
                            );
                          })}
                        </div>

                        {isAnswered && (
                          <div
                            className="mt-2.5 p-3 rounded-lg text-[12px]"
                            style={{
                              background: 'var(--surface)',
                              border: '1px solid var(--border)',
                              color: 'var(--ink)',
                            }}
                          >
                            <span className="font-semibold" style={{ color: 'var(--accent)' }}>Explanation: </span>
                            <span>{parseProvenanceTags(q.explanation)}</span>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}

              {/* TOOL 4: MIND MAP */}
              {toolType === 'mindmap' && (
                <div className="space-y-4">
                  <div
                    className="p-5 rounded-xl"
                    style={{
                      background: 'var(--canvas-alt)',
                      border: '1px solid var(--border)',
                    }}
                  >
                    <h3 className="text-[15px] font-bold mb-4 flex items-center gap-2" style={{ color: 'var(--ink)' }}>
                      <Network className="w-4 h-4" style={{ color: 'var(--accent)' }} />
                      <span>{data.name || 'Concept Hierarchy'}</span>
                    </h3>

                    <div className="space-y-4 pl-2">
                      {data.children?.map((cat: any, cIdx: number) => (
                        <div
                          key={cIdx}
                          className="pl-4 space-y-2"
                          style={{ borderLeft: '2px solid var(--accent)' }}
                        >
                          <h4 className="text-[13px] font-bold" style={{ color: 'var(--ink)' }}>
                            {cat.name}
                          </h4>
                          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                            {cat.children?.map((sub: any, sIdx: number) => (
                              <div
                                key={sIdx}
                                className="p-3 rounded-lg text-[12px]"
                                style={{
                                  background: 'var(--surface)',
                                  border: '1px solid var(--border)',
                                }}
                              >
                                <p className="font-semibold" style={{ color: 'var(--ink)' }}>
                                  {sub.name}
                                </p>
                                {sub.detail && (
                                  <p className="text-[11px] mt-1 leading-snug" style={{ color: 'var(--ink-muted)' }}>
                                    {parseProvenanceTags(sub.detail)}
                                  </p>
                                )}
                              </div>
                            ))}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              )}

              {/* TOOL 5: STUDY NOTES */}
              {toolType === 'notes' && (
                <div className="text-[13px] leading-relaxed space-y-3" style={{ color: 'var(--ink)' }}>
                  <ReactMarkdown
                    remarkPlugins={[remarkGfm]}
                    components={{
                      p: ({ children }) => <p className="mb-2 leading-relaxed">{children}</p>,
                      h2: ({ children }) => (
                        <h2 className="text-[15px] font-bold mt-4 mb-2 pb-1" style={{ borderBottom: '1px solid var(--border)' }}>
                          {children}
                        </h2>
                      ),
                      h3: ({ children }) => <h3 className="text-[13px] font-bold mt-3 mb-1">{children}</h3>,
                      li: ({ children }) => <li className="my-0.5">{children}</li>,
                      ul: ({ children }) => <ul className="list-disc pl-5 my-2">{children}</ul>,
                      blockquote: ({ children }) => (
                        <blockquote className="pl-3 italic my-2" style={{ borderLeft: '3px solid var(--accent)', color: 'var(--ink-muted)' }}>
                          {children}
                        </blockquote>
                      ),
                    }}
                  >
                    {data.markdown_content || ''}
                  </ReactMarkdown>
                </div>
              )}

              {/* TOOL 6: DATA TABLE */}
              {toolType === 'datatable' && (
                <div className="space-y-3">
                  <div>
                    <h3 className="text-[15px] font-bold" style={{ color: 'var(--ink)' }}>
                      {data.title || 'Data Table'}
                    </h3>
                    {data.description && (
                      <p className="text-[12px] mt-0.5" style={{ color: 'var(--ink-muted)' }}>
                        {data.description}
                      </p>
                    )}
                  </div>

                  <div className="overflow-x-auto rounded-xl" style={{ border: '1px solid var(--border)' }}>
                    <table className="w-full text-left text-[12px] border-collapse">
                      <thead>
                        <tr style={{ background: 'var(--canvas-alt)', borderBottom: '1px solid var(--border)' }}>
                          {data.columns?.map((col: string, idx: number) => (
                            <th key={idx} className="p-3 font-semibold" style={{ color: 'var(--ink)' }}>
                              {col}
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {data.rows?.map((row: string[], rIdx: number) => (
                          <tr
                            key={rIdx}
                            style={{
                              borderBottom: '1px solid var(--border-muted)',
                              background: rIdx % 2 === 0 ? 'var(--surface)' : 'var(--canvas-alt)',
                            }}
                          >
                            {row.map((cell, cIdx) => (
                              <td key={cIdx} className="p-3" style={{ color: 'var(--ink)' }}>
                                {parseProvenanceTags(cell)}
                              </td>
                            ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
