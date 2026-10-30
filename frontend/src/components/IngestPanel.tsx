'use client';
import React, { useState, useRef, useEffect } from 'react';
import {
  Link as LinkIcon,
  Loader2,
  CheckCircle2,
  BookOpen,
  AlertCircle,
  AlertTriangle,
  Plus,
  Trash2,
  RotateCcw,
  ExternalLink,
  ChevronDown,
  ChevronUp,
  RefreshCw,
  Scissors,
} from 'lucide-react';
import type { IngestResponse, SourceInfo } from '@/types';
import { ProvenanceTag } from './ProvenanceTag';

const MAX_SOURCES = 5;

interface IngestPanelProps {
  projectId?: string | null;
  onIngested: (resp: IngestResponse | null) => void;
}

interface SourceField {
  id: string;
  url: string;
  error?: string;
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

function isValidHttpUrl(str: string): boolean {
  if (!str) return false;
  const trimmed = str.trim();
  try {
    const url = new URL(trimmed);
    return (
      (url.protocol === 'http:' || url.protocol === 'https:') &&
      Boolean(url.hostname) &&
      url.hostname.includes('.')
    );
  } catch {
    return false;
  }
}

function normalizeUrlKey(url: string): string {
  try {
    const parsed = new URL(url.trim());
    const path = parsed.pathname === '/' ? '' : parsed.pathname.replace(/\/+$/, '');
    return `${parsed.protocol}//${parsed.hostname.toLowerCase()}${path}`;
  } catch {
    return url.trim().toLowerCase().replace(/\/+$/, '');
  }
}

function shortenUrl(url: string, maxLength = 36): string {
  try {
    const parsed = new URL(url);
    const domain = parsed.hostname.replace('www.', '');
    const path = parsed.pathname === '/' ? '' : parsed.pathname;
    const combined = `${domain}${path}`;
    return combined.length > maxLength ? `${combined.slice(0, maxLength - 3)}...` : combined;
  } catch {
    return url.length > maxLength ? `${url.slice(0, maxLength - 3)}...` : url;
  }
}

export function IngestPanel({ projectId, onIngested }: IngestPanelProps) {
  // Exactly one empty source URL field by default
  const [sources, setSources] = useState<SourceField[]>([
    { id: 'source-1', url: '' },
  ]);
  const [topicName, setTopicName] = useState('');
  const [loading, setLoading] = useState(false);
  const [globalError, setGlobalError] = useState<string | null>(null);
  const [result, setResult] = useState<IngestResponse | null>(null);
  const [step, setStep] = useState<string>('');
  const [showFailedSection, setShowFailedSection] = useState(true);
  const [actionInProgress, setActionInProgress] = useState<string | null>(null);

  // Auto-load project sources when project changes
  useEffect(() => {
    if (!projectId) {
      setResult(null);
      return;
    }
    fetch(`/api/projects/${projectId}/sources`, { credentials: 'include' })
      .then((res) => (res.ok ? res.json() : []))
      .then((sourcesList: SourceInfo[]) => {
        if (sourcesList && sourcesList.length > 0) {
          const successSources = sourcesList.filter((s) => s.status === 'success');
          const failedSources = sourcesList.filter((s) => s.status === 'failed');
          const totalChunks = successSources.reduce((acc, s) => acc + (s.chunk_count || s.chunks_indexed || 0), 0);
          const mockResp: IngestResponse = {
            session_id: projectId,
            topic_name: '',
            total_submitted: sourcesList.length,
            successful_count: successSources.length,
            failed_count: failedSources.length,
            total_chunks: totalChunks,
            sources: sourcesList,
          };
          setResult(mockResp);
          onIngested(mockResp);
        } else {
          setResult(null);
          onIngested(null);
        }
      })
      .catch(() => {});
  }, [projectId]);

  // Input refs for auto-focusing on validation failure
  const inputRefs = useRef<Record<string, HTMLInputElement | null>>({});

  // 1 & 2: Validate Before Adding a Source
  const addSourceField = () => {
    if (loading) return;
    if (sources.length >= MAX_SOURCES) return;

    // Check whether the LAST source field contains a URL
    const lastSource = sources[sources.length - 1];
    const lastUrl = lastSource.url.trim();

    if (!lastUrl) {
      setSources((prev) =>
        prev.map((s, idx) =>
          idx === prev.length - 1
            ? { ...s, error: 'Please enter a source URL before adding another source.' }
            : s
        )
      );
      inputRefs.current[lastSource.id]?.focus();
      return;
    }

    if (!isValidHttpUrl(lastUrl)) {
      setSources((prev) =>
        prev.map((s, idx) =>
          idx === prev.length - 1
            ? { ...s, error: 'Please enter a valid HTTP or HTTPS URL.' }
            : s
        )
      );
      inputRefs.current[lastSource.id]?.focus();
      return;
    }

    // Clear any previous error and add new field
    const newId = `source-${Date.now()}-${Math.random().toString(36).substr(2, 4)}`;
    setSources((prev) => [
      ...prev.map((s, idx) => (idx === prev.length - 1 ? { ...s, error: undefined } : s)),
      { id: newId, url: '' },
    ]);

    // Focus the newly created field on next tick
    setTimeout(() => {
      inputRefs.current[newId]?.focus();
    }, 50);
  };

  // Remove field while preserving other values
  const removeSourceField = (id: string) => {
    if (sources.length <= 1 || loading) return; // Always keep at least one field visible
    setSources((prev) => prev.filter((s) => s.id !== id));
  };

  // Automatically clear error when user corrects URL
  const updateSourceUrl = (id: string, val: string) => {
    setSources((prev) =>
      prev.map((s) => (s.id === id ? { ...s, url: val, error: undefined } : s))
    );
  };

  // 3: Validate Before Indexing
  const handleIngest = async () => {
    if (loading) return; // Prevent concurrent rapid clicks

    setGlobalError(null);

    // Identify non-empty fields (ignore unused empty fields if some are filled)
    const filledFields = sources.filter((s) => s.url.trim() !== '');

    if (filledFields.length === 0) {
      // Require at least one valid, non-empty URL
      setSources((prev) =>
        prev.map((s, idx) =>
          idx === 0
            ? { ...s, error: 'Please enter at least one source URL.' }
            : s
        )
      );
      inputRefs.current[sources[0].id]?.focus();
      return;
    }

    // Validate syntax and detect duplicates among non-empty URLs
    let hasValidationError = false;
    const seenNorms = new Set<string>();

    const validated = sources.map((s) => {
      const trimmed = s.url.trim();
      if (!trimmed) {
        // Unused empty field is ignored without error
        return { ...s, error: undefined };
      }
      if (!isValidHttpUrl(trimmed)) {
        hasValidationError = true;
        return { ...s, error: 'Please enter a valid HTTP or HTTPS URL.' };
      }
      const norm = normalizeUrlKey(trimmed);
      if (seenNorms.has(norm)) {
        hasValidationError = true;
        return { ...s, error: 'Duplicate URL in your submission.' };
      }
      seenNorms.add(norm);
      return { ...s, error: undefined };
    });

    setSources(validated);
    if (hasValidationError) return;

    // Gather valid URLs (max 5)
    const urlsToIngest = sources
      .map((s) => s.url.trim())
      .filter(Boolean)
      .slice(0, MAX_SOURCES);

    setLoading(true);
    setStep('Validating source URLs…');

    try {
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 180_000);

      let resp: Response;
      try {
        setStep('Scraping content & enforcing limits…');
        const payload: Record<string, any> = {
          source_urls: urlsToIngest,
          topic_name: topicName.trim(),
        };

        if (projectId) {
          payload.project_id = projectId;
        } else if (result?.session_id) {
          payload.session_id = result.session_id;
        }

        resp = await fetch('/api/ingest', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          credentials: 'include',
          body: JSON.stringify(payload),
          signal: controller.signal,
        });
      } finally {
        clearTimeout(timeout);
      }

      setStep('Indexing embeddings…');

      if (!resp.ok) {
        const errData = await safeJson(resp);
        throw new Error(
          typeof errData === 'object'
            ? errData.detail || errData.message || JSON.stringify(errData)
            : String(errData)
        );
      }

      const data: IngestResponse = await safeJson(resp);
      setResult(data);
      onIngested(data.successful_count > 0 ? data : null);
    } catch (e: any) {
      if (e.name === 'AbortError') {
        setGlobalError('Request timed out after 3 minutes. The sites may be slow to respond.');
      } else {
        setGlobalError(e.message || 'Failed to index sources');
      }
    } finally {
      setLoading(false);
      setStep('');
    }
  };

  // Retry an individual failed source
  const handleRetrySource = async (failedSource: SourceInfo) => {
    const targetUrl = failedSource.original_url || failedSource.url;
    if (!targetUrl || actionInProgress) return;

    setActionInProgress(`retry-${targetUrl}`);
    setGlobalError(null);

    try {
      const payload: Record<string, any> = {
        source_urls: [targetUrl],
        topic_name: topicName || result?.topic_name || '',
      };

      if (projectId) {
        payload.project_id = projectId;
      } else if (result?.session_id) {
        payload.session_id = result.session_id;
      }

      const resp = await fetch('/api/ingest', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify(payload),
      });

      if (!resp.ok) {
        const errData = await safeJson(resp);
        throw new Error(errData.detail || 'Retry failed');
      }

      const data: IngestResponse = await safeJson(resp);
      setResult(data);
      onIngested(data.successful_count > 0 ? data : null);
    } catch (e: any) {
      setGlobalError(`Retry failed for ${shortenUrl(targetUrl)}: ${e.message}`);
    } finally {
      setActionInProgress(null);
    }
  };

  // Remove an active source from the topic and FAISS index
  const handleRemoveIndexedSource = async (sourceId: string) => {
    if (!result?.session_id || actionInProgress) return;

    setActionInProgress(`remove-${sourceId}`);
    setGlobalError(null);

    try {
      const resp = await fetch(
        `/api/sources/${encodeURIComponent(result.session_id)}/${encodeURIComponent(sourceId)}`,
        { method: 'DELETE' }
      );

      if (!resp.ok) {
        const errData = await safeJson(resp);
        throw new Error(errData.detail || 'Failed to remove source');
      }

      const data: IngestResponse = await safeJson(resp);
      setResult(data);
      onIngested(data.successful_count > 0 ? data : null);
    } catch (e: any) {
      setGlobalError(`Failed to remove source: ${e.message}`);
    } finally {
      setActionInProgress(null);
    }
  };

  // Reset to create a new topic
  const handleReset = () => {
    setResult(null);
    setSources([{ id: 'source-1', url: '' }]);
    setTopicName('');
    setGlobalError(null);
    onIngested(null);
  };

  const successfulSources = result?.sources.filter((s) => s.status === 'success') || [];
  const failedSources = result?.sources.filter((s) => s.status === 'failed') || [];

  return (
    <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-5 md:p-6 transition-all">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <BookOpen className="w-5 h-5 text-brand-600" />
          <h2 className="text-base font-semibold text-slate-800">Load Topic</h2>
        </div>
        {result && (
          <button
            onClick={handleReset}
            className="text-xs text-slate-400 hover:text-slate-600 transition-colors flex items-center gap-1"
            title="Start a new topic"
          >
            <RefreshCw className="w-3 h-3" />
            New Topic
          </button>
        )}
      </div>

      <div className="space-y-4">
        {/* Topic Name */}
        <div>
          <label className="text-xs font-medium text-slate-500 mb-1 block">
            Topic Name <span className="text-slate-400 font-normal">(optional)</span>
          </label>
          <input
            type="text"
            value={topicName}
            onChange={(e) => setTopicName(e.target.value)}
            disabled={loading}
            placeholder="e.g. Retrieval-Augmented Generation"
            className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 disabled:opacity-60 disabled:bg-slate-50"
          />
        </div>

        {/* Dynamic Source Inputs with (current/5) Count */}
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <label className="text-xs font-semibold text-slate-700">
              Source URLs <span className="text-brand-600 font-medium">({sources.length}/{MAX_SOURCES})</span>
            </label>
            <button
              type="button"
              onClick={addSourceField}
              disabled={loading || sources.length >= MAX_SOURCES}
              className="text-xs font-medium text-brand-600 hover:text-brand-700 flex items-center gap-1 transition-colors disabled:opacity-40 disabled:hover:text-brand-600"
            >
              <Plus className="w-3.5 h-3.5" />
              Add Source
            </button>
          </div>

          {/* Subtle message when 5 sources reached */}
          {sources.length >= MAX_SOURCES && (
            <p className="text-[11px] text-slate-400 italic">
              Maximum of 5 sources allowed.
            </p>
          )}

          {sources.map((s, idx) => (
            <div key={s.id} className="space-y-1">
              <div className="flex items-center gap-1.5">
                <span className="text-xs font-medium text-slate-400 w-16 flex-shrink-0">
                  Source {idx + 1}
                </span>
                <div className="relative flex-1">
                  <input
                    ref={(el) => {
                      inputRefs.current[s.id] = el;
                    }}
                    type="url"
                    value={s.url}
                    onChange={(e) => updateSourceUrl(s.id, e.target.value)}
                    disabled={loading}
                    placeholder="https://..."
                    className={`w-full border rounded-lg pl-3 pr-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 disabled:opacity-60 disabled:bg-slate-50 ${
                      s.error ? 'border-red-300 bg-red-50/40 text-red-900' : 'border-slate-200'
                    }`}
                    onKeyDown={(e) => e.key === 'Enter' && !loading && handleIngest()}
                  />
                </div>
                {/* Remove button beside each source input */}
                <button
                  type="button"
                  onClick={() => removeSourceField(s.id)}
                  disabled={sources.length <= 1 || loading}
                  className="p-1.5 text-slate-400 hover:text-red-500 hover:bg-red-50 rounded-lg transition-colors disabled:opacity-20 disabled:hover:bg-transparent disabled:hover:text-slate-400"
                  title={sources.length <= 1 ? 'At least one source is required' : 'Remove this source'}
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>

              {/* Inline validation error with auto-clear on edit */}
              {s.error && (
                <p className="text-xs text-red-600 pl-16 flex items-center gap-1 animate-fadeIn">
                  <AlertCircle className="w-3 h-3 flex-shrink-0" />
                  {s.error}
                </p>
              )}
            </div>
          ))}
        </div>

        {/* Live step indicator */}
        {loading && step && (
          <p className="text-xs text-brand-600 flex items-center gap-1.5 bg-brand-50 border border-brand-100 rounded-lg px-2.5 py-1.5">
            <Loader2 className="w-3.5 h-3.5 animate-spin flex-shrink-0" />
            <span>{step}</span>
          </p>
        )}

        {/* Global error banner */}
        {globalError && (
          <div className="flex items-start gap-2 bg-red-50 border border-red-200 rounded-lg p-2.5">
            <AlertCircle className="w-4 h-4 text-red-500 flex-shrink-0 mt-0.5" />
            <p className="text-xs text-red-700 break-words">{globalError}</p>
          </div>
        )}

        {/* Main Action Button */}
        <button
          onClick={handleIngest}
          disabled={loading || sources.every((s) => !s.url.trim())}
          className="w-full py-2.5 bg-brand-600 hover:bg-brand-700 disabled:opacity-50 text-white text-sm font-semibold rounded-lg transition-all shadow-sm flex items-center justify-center gap-2"
        >
          {loading ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin" />
              Indexing Sources...
            </>
          ) : (
            <>
              <LinkIcon className="w-4 h-4" />
              Load &amp; Index Sources
            </>
          )}
        </button>

        {!loading && !result && (
          <p className="text-xs text-slate-400 text-center">
            ⏱ Supports up to 5 sources (max 2 MB per source)
          </p>
        )}
      </div>

      {/* Results Section */}
      {result && (
        <div className="mt-5 pt-4 border-t border-slate-100 space-y-3">
          {/* Summary Status Header */}
          {result.successful_count > 0 ? (
            <div
              className={`flex items-center gap-1.5 text-sm font-semibold rounded-lg px-3 py-2 ${
                result.failed_count > 0
                  ? 'bg-amber-50 border border-amber-200 text-amber-800'
                  : 'bg-emerald-50 border border-emerald-200 text-emerald-700'
              }`}
            >
              {result.failed_count > 0 ? (
                <>
                  <AlertTriangle className="w-4 h-4 flex-shrink-0 text-amber-600" />
                  <span>
                    {result.successful_count} source{result.successful_count !== 1 ? 's' : ''} indexed successfully;{' '}
                    {result.failed_count} source{result.failed_count !== 1 ? 's' : ''} failed.
                  </span>
                </>
              ) : (
                <>
                  <CheckCircle2 className="w-4 h-4 flex-shrink-0 text-emerald-600" />
                  <span>
                    Indexed {result.total_chunks} chunk{result.total_chunks !== 1 ? 's' : ''} from{' '}
                    {result.successful_count} source{result.successful_count !== 1 ? 's' : ''}.
                  </span>
                </>
              )}
            </div>
          ) : (
            <div className="flex items-center gap-1.5 text-red-700 text-sm font-semibold bg-red-50 border border-red-200 rounded-lg px-3 py-2">
              <AlertCircle className="w-4 h-4 flex-shrink-0 text-red-600" />
              <span>All submitted sources failed to index. Check errors below.</span>
            </div>
          )}

          {/* Successfully Indexed Sources List */}
          {successfulSources.length > 0 && (
            <div className="space-y-1.5">
              <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
                Active Sources ({successfulSources.length})
              </p>
              {successfulSources.map((s) => (
                <div
                  key={s.source_id}
                  className="group flex items-center gap-2 p-2 rounded-lg border border-slate-200 bg-slate-50/50 hover:bg-white hover:border-slate-300 transition-all text-xs"
                >
                  <ProvenanceTag sourceId={s.source_id} />
                  <div className="flex-1 min-w-0">
                    <p className="font-medium text-slate-800 truncate" title={s.title}>
                      {s.title || s.url}
                    </p>
                    <div className="flex items-center gap-1.5">
                      <a
                        href={s.resolved_url || s.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-slate-400 hover:text-brand-600 truncate flex items-center gap-1 text-[11px]"
                        title={s.resolved_url || s.url}
                      >
                        <span>{shortenUrl(s.resolved_url || s.url)}</span>
                        <ExternalLink className="w-2.5 h-2.5 flex-shrink-0" />
                      </a>
                      {/* Truncation badge if content exceeded limit */}
                      {s.truncated && (
                        <span
                          className="inline-flex items-center gap-0.5 text-[10px] bg-amber-50 text-amber-700 border border-amber-200 px-1 py-0.2 rounded"
                          title="The page was partially indexed because its content exceeded the configured limit."
                        >
                          <Scissors className="w-2.5 h-2.5" />
                          Truncated
                        </span>
                      )}
                    </div>
                  </div>
                  <span className="bg-slate-200/70 text-slate-600 px-1.5 py-0.5 rounded text-[10px] font-mono flex-shrink-0">
                    {s.chunk_count} chunks
                  </span>
                  {/* Remove indexed source button */}
                  <button
                    onClick={() => handleRemoveIndexedSource(s.source_id)}
                    disabled={actionInProgress !== null}
                    className="p-1 text-slate-400 hover:text-red-500 hover:bg-red-50 rounded transition-colors"
                    title={`Remove ${s.source_id} from topic`}
                  >
                    {actionInProgress === `remove-${s.source_id}` ? (
                      <Loader2 className="w-3.5 h-3.5 animate-spin text-slate-500" />
                    ) : (
                      <Trash2 className="w-3.5 h-3.5" />
                    )}
                  </button>
                </div>
              ))}
            </div>
          )}

          {/* Expandable Failed Sources Section */}
          {failedSources.length > 0 && (
            <div className="border border-red-200 bg-red-50/40 rounded-xl overflow-hidden text-xs">
              <button
                type="button"
                onClick={() => setShowFailedSection(!showFailedSection)}
                className="w-full flex items-center justify-between p-2.5 text-left font-medium text-red-800 hover:bg-red-100/50 transition-colors"
              >
                <div className="flex items-center gap-1.5">
                  <AlertTriangle className="w-3.5 h-3.5 text-red-600" />
                  <span>
                    Failed Sources ({failedSources.length})
                  </span>
                </div>
                {showFailedSection ? (
                  <ChevronUp className="w-3.5 h-3.5 text-red-500" />
                ) : (
                  <ChevronDown className="w-3.5 h-3.5 text-red-500" />
                )}
              </button>

              {showFailedSection && (
                <div className="p-2.5 pt-0 space-y-2 border-t border-red-100">
                  {failedSources.map((f, i) => (
                    <div
                      key={i}
                      className="bg-white rounded-lg border border-red-200 p-2 text-xs space-y-1 shadow-2xs"
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span className="font-mono text-slate-600 truncate flex-1" title={f.original_url || f.url}>
                          {shortenUrl(f.original_url || f.url, 40)}
                        </span>
                        <button
                          type="button"
                          onClick={() => handleRetrySource(f)}
                          disabled={actionInProgress !== null}
                          className="px-2 py-1 bg-brand-50 hover:bg-brand-100 text-brand-700 border border-brand-200 rounded font-medium text-[11px] flex items-center gap-1 transition-colors disabled:opacity-50"
                        >
                          {actionInProgress === `retry-${f.original_url || f.url}` ? (
                            <Loader2 className="w-3 h-3 animate-spin" />
                          ) : (
                            <RotateCcw className="w-3 h-3" />
                          )}
                          Retry
                        </button>
                      </div>
                      <p className="text-red-700 text-[11px] bg-red-50/80 p-1.5 rounded border border-red-100 break-words">
                        {f.error || 'Failed to fetch content.'}
                      </p>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
