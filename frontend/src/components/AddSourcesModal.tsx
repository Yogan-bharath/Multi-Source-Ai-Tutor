'use client';
import React, { useState, useRef } from 'react';
import {
  X,
  Globe,
  Upload,
  FileText,
  Plus,
  Trash2,
  Loader2,
  AlertCircle,
  CheckCircle2,
  FileUp,
  File,
} from 'lucide-react';
import type { SourceInfo } from '@/types';

interface AddSourcesModalProps {
  isOpen: boolean;
  onClose: () => void;
  projectId: string;
  projectName?: string;
  onSourcesAdded: () => void;
}

type TabType = 'urls' | 'upload' | 'text';

function isValidHttpUrl(str: string): boolean {
  if (!str) return false;
  try {
    const url = new URL(str.trim());
    return (
      (url.protocol === 'http:' || url.protocol === 'https:') &&
      Boolean(url.hostname) &&
      url.hostname.includes('.')
    );
  } catch {
    return false;
  }
}

export function AddSourcesModal({
  isOpen,
  onClose,
  projectId,
  projectName,
  onSourcesAdded,
}: AddSourcesModalProps) {
  const [activeTab, setActiveTab] = useState<TabType>('urls');

  // Tab 1: URLs
  const [urlFields, setUrlFields] = useState<string[]>(['']);
  const [urlErrors, setUrlErrors] = useState<Record<number, string>>({});

  // Tab 2: Upload File
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [fileTitle, setFileTitle] = useState('');
  const [fileError, setFileError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Tab 3: Paste Text
  const [pastedTitle, setPastedTitle] = useState('');
  const [pastedText, setPastedText] = useState('');
  const [textError, setTextError] = useState<string | null>(null);

  // Global loading & status
  const [loading, setLoading] = useState(false);
  const [globalError, setGlobalError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  if (!isOpen) return null;

  // --- Handlers for Tab 1: URLs ---
  const handleAddUrlField = () => {
    if (urlFields.length >= 5) return;
    const lastUrl = urlFields[urlFields.length - 1].trim();
    if (!lastUrl) {
      setUrlErrors((prev) => ({ ...prev, [urlFields.length - 1]: 'Please enter a URL first' }));
      return;
    }
    if (!isValidHttpUrl(lastUrl)) {
      setUrlErrors((prev) => ({ ...prev, [urlFields.length - 1]: 'Enter a valid URL (http:// or https://)' }));
      return;
    }
    setUrlFields((prev) => [...prev, '']);
  };

  const handleRemoveUrlField = (index: number) => {
    if (urlFields.length <= 1) {
      setUrlFields(['']);
      setUrlErrors({});
      return;
    }
    setUrlFields((prev) => prev.filter((_, i) => i !== index));
    const nextErrors: Record<number, string> = {};
    Object.entries(urlErrors).forEach(([k, v]) => {
      const idx = Number(k);
      if (idx < index) nextErrors[idx] = v;
      else if (idx > index) nextErrors[idx - 1] = v;
    });
    setUrlErrors(nextErrors);
  };

  const handleUrlChange = (index: number, val: string) => {
    setUrlFields((prev) => {
      const copy = [...prev];
      copy[index] = val;
      return copy;
    });
    if (urlErrors[index]) {
      setUrlErrors((prev) => {
        const copy = { ...prev };
        delete copy[index];
        return copy;
      });
    }
  };

  const submitUrls = async () => {
    setGlobalError(null);
    setSuccessMsg(null);
    const validUrls: string[] = [];
    const errors: Record<number, string> = {};

    urlFields.forEach((u, i) => {
      const trimmed = u.trim();
      if (!trimmed) {
        errors[i] = 'URL cannot be empty';
      } else if (!isValidHttpUrl(trimmed)) {
        errors[i] = 'Enter a valid URL (http:// or https://)';
      } else if (validUrls.includes(trimmed)) {
        errors[i] = 'Duplicate URL entered';
      } else {
        validUrls.push(trimmed);
      }
    });

    if (Object.keys(errors).length > 0) {
      setUrlErrors(errors);
      return;
    }

    setLoading(true);
    try {
      const res = await fetch('/api/ingest', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({
          project_id: projectId,
          source_urls: validUrls,
        }),
      });

      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || 'Failed to index URLs');
      }

      // Always notify parent so any newly saved sources (success or failed) appear in sidebar
      onSourcesAdded();

      if (data.successful_count > 0) {
        setSuccessMsg(`Successfully indexed ${data.successful_count} source(s)!`);
        setTimeout(() => {
          onClose();
        }, 1200);
      } else {
        setGlobalError('All submitted URLs failed to index. Check permissions or network access, or review them in the Sources sidebar.');
      }
    } catch (e: any) {
      setGlobalError(e.message || 'Error indexing sources');
    } finally {
      setLoading(false);
    }
  };

  // --- Handlers for Tab 2: File Upload ---
  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (!f) return;
    const ext = f.name.toLowerCase().split('.').pop();
    if (!['pdf', 'txt', 'md', 'markdown'].includes(ext || '')) {
      setFileError('Allowed formats: PDF (.pdf), Text (.txt), Markdown (.md)');
      setSelectedFile(null);
      return;
    }
    if (f.size > 20 * 1024 * 1024) {
      setFileError('File size exceeds maximum limit of 20MB');
      setSelectedFile(null);
      return;
    }
    setFileError(null);
    setSelectedFile(f);
    if (!fileTitle) {
      setFileTitle(f.name.replace(/\.[^/.]+$/, ''));
    }
  };

  const submitFile = async () => {
    if (!selectedFile) {
      setFileError('Please select a file to upload');
      return;
    }
    setLoading(true);
    setGlobalError(null);
    setSuccessMsg(null);

    const formData = new FormData();
    formData.append('project_id', projectId);
    formData.append('file', selectedFile);
    if (fileTitle.trim()) {
      formData.append('title', fileTitle.trim());
    }

    try {
      const res = await fetch('/api/ingest/upload', {
        method: 'POST',
        credentials: 'include',
        body: formData,
      });

      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || 'Failed to upload document');
      }

      setSuccessMsg(`Document "${fileTitle || selectedFile.name}" indexed successfully!`);
      onSourcesAdded();
      setTimeout(() => {
        onClose();
      }, 1200);
    } catch (e: any) {
      setGlobalError(e.message || 'Error processing document');
    } finally {
      setLoading(false);
    }
  };

  // --- Handlers for Tab 3: Paste Text ---
  const submitText = async () => {
    const cleanText = pastedText.trim();
    if (!cleanText) {
      setTextError('Please paste or type study notes first');
      return;
    }
    setLoading(true);
    setGlobalError(null);
    setSuccessMsg(null);

    try {
      const res = await fetch('/api/ingest/text', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({
          project_id: projectId,
          title: pastedTitle.trim() || 'Pasted Study Note',
          text: cleanText,
        }),
      });

      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || 'Failed to index text');
      }

      setSuccessMsg('Pasted study notes indexed into project vectors!');
      onSourcesAdded();
      setTimeout(() => {
        onClose();
      }, 1200);
    } catch (e: any) {
      setGlobalError(e.message || 'Error saving study note');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 animate-fadeIn"
      style={{ background: 'rgba(0, 0, 0, 0.65)', backdropFilter: 'blur(4px)' }}
      onKeyDown={(e) => e.key === 'Escape' && !loading && onClose()}
    >
      <div
        className="rounded-2xl shadow-modal w-full max-w-xl overflow-hidden flex flex-col max-h-[90vh] animate-scaleIn"
        style={{
          background: 'var(--surface-overlay)',
          border: '1px solid var(--border)',
          color: 'var(--ink)',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div
          className="flex items-center justify-between p-5"
          style={{ borderBottom: '1px solid var(--border)' }}
        >
          <div>
            <h3 className="text-[16px] font-bold leading-snug" style={{ color: 'var(--ink)' }}>
              Add Sources to Notebook
            </h3>
            <p className="text-[12px] mt-0.5" style={{ color: 'var(--ink-muted)' }}>
              Ground your AI tutor in web articles, documents, or personal research notes
            </p>
          </div>
          <button
            onClick={onClose}
            disabled={loading}
            className="p-1.5 rounded-lg transition-colors hover:opacity-80"
            style={{ color: 'var(--ink-faint)' }}
            title="Close dialog"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Source Selection Tabs */}
        <div
          className="flex px-5 pt-2 gap-3"
          style={{
            background: 'var(--canvas-alt)',
            borderBottom: '1px solid var(--border)',
          }}
        >
          <button
            onClick={() => {
              setActiveTab('urls');
              setGlobalError(null);
            }}
            className="flex items-center gap-2 pb-2.5 px-2 text-[12px] font-semibold border-b-2 transition-colors"
            style={{
              borderColor: activeTab === 'urls' ? 'var(--accent)' : 'transparent',
              color: activeTab === 'urls' ? 'var(--accent)' : 'var(--ink-muted)',
            }}
          >
            <Globe className="w-4 h-4" />
            <span>Websites / URLs</span>
          </button>
          <button
            onClick={() => {
              setActiveTab('upload');
              setGlobalError(null);
            }}
            className="flex items-center gap-2 pb-2.5 px-2 text-[12px] font-semibold border-b-2 transition-colors"
            style={{
              borderColor: activeTab === 'upload' ? 'var(--accent)' : 'transparent',
              color: activeTab === 'upload' ? 'var(--accent)' : 'var(--ink-muted)',
            }}
          >
            <Upload className="w-4 h-4" />
            <span>Upload Document</span>
          </button>
          <button
            onClick={() => {
              setActiveTab('text');
              setGlobalError(null);
            }}
            className="flex items-center gap-2 pb-2.5 px-2 text-[12px] font-semibold border-b-2 transition-colors"
            style={{
              borderColor: activeTab === 'text' ? 'var(--accent)' : 'transparent',
              color: activeTab === 'text' ? 'var(--accent)' : 'var(--ink-muted)',
            }}
          >
            <FileText className="w-4 h-4" />
            <span>Paste Notes</span>
          </button>
        </div>

        {/* Form Body */}
        <div className="p-6 overflow-y-auto flex-1 space-y-4">
          {globalError && (
            <div
              className="p-3 rounded-lg flex items-start gap-2.5 text-[12px]"
              style={{
                background: 'var(--negative-muted)',
                border: '1px solid var(--negative)',
                color: 'var(--negative)',
              }}
            >
              <AlertCircle className="w-4 h-4 flex-shrink-0 mt-0.5" />
              <span>{globalError}</span>
            </div>
          )}

          {successMsg && (
            <div
              className="p-3 rounded-lg flex items-start gap-2.5 text-[12px]"
              style={{
                background: 'var(--positive-muted)',
                border: '1px solid var(--positive)',
                color: 'var(--positive)',
              }}
            >
              <CheckCircle2 className="w-4 h-4 flex-shrink-0 mt-0.5" />
              <span>{successMsg}</span>
            </div>
          )}

          {/* TAB 1: WEBSITES / URLS */}
          {activeTab === 'urls' && (
            <div className="space-y-3">
              <div className="flex items-center justify-between text-[12px]" style={{ color: 'var(--ink-muted)' }}>
                <span>Enter up to 5 article, documentation, or tutorial URLs</span>
                <span className="font-mono text-[11px]" style={{ color: 'var(--ink-faint)' }}>
                  {urlFields.length}/5
                </span>
              </div>

              <div className="space-y-2.5">
                {urlFields.map((url, idx) => (
                  <div key={idx} className="space-y-1">
                    <div className="flex items-center gap-2">
                      <div className="relative flex-1">
                        <span
                          className="absolute left-3 top-2.5 text-[11px] font-mono"
                          style={{ color: 'var(--ink-faint)' }}
                        >
                          {idx + 1}.
                        </span>
                        <input
                          type="url"
                          value={url}
                          placeholder="https://example.com/topic"
                          onChange={(e) => handleUrlChange(idx, e.target.value)}
                          disabled={loading}
                          className="w-full pl-8 pr-3 py-2 text-[12px] rounded-lg focus:outline-none transition-colors"
                          style={{
                            background: 'var(--canvas-alt)',
                            border: `1px solid ${urlErrors[idx] ? 'var(--negative)' : 'var(--border)'}`,
                            color: 'var(--ink)',
                          }}
                        />
                      </div>
                      <button
                        onClick={() => handleRemoveUrlField(idx)}
                        disabled={loading || urlFields.length <= 1}
                        className="p-2 rounded-lg transition-colors disabled:opacity-30 hover:opacity-80"
                        style={{ color: 'var(--ink-faint)' }}
                        title="Remove source URL"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                    {urlErrors[idx] && (
                      <p className="text-[11px] pl-8" style={{ color: 'var(--negative)' }}>
                        {urlErrors[idx]}
                      </p>
                    )}
                  </div>
                ))}
              </div>

              {urlFields.length < 5 && (
                <button
                  onClick={handleAddUrlField}
                  disabled={loading}
                  className="flex items-center gap-1.5 text-[12px] font-medium py-1 px-2 rounded-lg transition-colors hover:opacity-80"
                  style={{ color: 'var(--accent)' }}
                >
                  <Plus className="w-3.5 h-3.5" />
                  <span>Add another URL</span>
                </button>
              )}
            </div>
          )}

          {/* TAB 2: UPLOAD FILE */}
          {activeTab === 'upload' && (
            <div className="space-y-4">
              <input
                ref={fileInputRef}
                type="file"
                accept=".pdf,.txt,.md,.markdown"
                onChange={handleFileSelect}
                className="hidden"
              />

              {!selectedFile ? (
                <div
                  onClick={() => fileInputRef.current?.click()}
                  className="border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-colors"
                  style={{
                    borderColor: 'var(--border)',
                    background: 'var(--canvas-alt)',
                  }}
                >
                  <FileUp className="w-9 h-9 mx-auto mb-2" style={{ color: 'var(--ink-faint)' }} />
                  <p className="text-[13px] font-semibold" style={{ color: 'var(--ink)' }}>
                    Click to select or drag & drop document
                  </p>
                  <p className="text-[11px] mt-1" style={{ color: 'var(--ink-muted)' }}>
                    Supports PDF (.pdf), Plain Text (.txt), and Markdown (.md) up to 20MB
                  </p>
                </div>
              ) : (
                <div
                  className="rounded-xl p-3.5 flex items-center justify-between"
                  style={{
                    background: 'var(--canvas-alt)',
                    border: '1px solid var(--border)',
                  }}
                >
                  <div className="flex items-center gap-3 truncate mr-2">
                    <div
                      className="w-9 h-9 rounded-lg flex items-center justify-center flex-shrink-0"
                      style={{
                        background: 'var(--accent-muted)',
                        color: 'var(--accent)',
                      }}
                    >
                      <File className="w-5 h-5" />
                    </div>
                    <div className="truncate">
                      <p className="text-[12px] font-medium truncate" style={{ color: 'var(--ink)' }}>
                        {selectedFile.name}
                      </p>
                      <p className="text-[11px]" style={{ color: 'var(--ink-faint)' }}>
                        {(selectedFile.size / 1024 / 1024).toFixed(2)} MB
                      </p>
                    </div>
                  </div>
                  <button
                    onClick={() => setSelectedFile(null)}
                    disabled={loading}
                    className="p-1.5 rounded-lg transition-colors hover:opacity-80"
                    style={{ color: 'var(--ink-faint)' }}
                    title="Remove file"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              )}

              {fileError && (
                <p className="text-[11px]" style={{ color: 'var(--negative)' }}>
                  {fileError}
                </p>
              )}

              {selectedFile && (
                <div>
                  <label className="block text-[12px] font-semibold mb-1" style={{ color: 'var(--ink)' }}>
                    Document Title (Optional)
                  </label>
                  <input
                    type="text"
                    value={fileTitle}
                    onChange={(e) => setFileTitle(e.target.value)}
                    placeholder="e.g. Research Paper or Lecture Notes"
                    disabled={loading}
                    className="w-full px-3 py-2 text-[12px] rounded-lg focus:outline-none transition-colors"
                    style={{
                      background: 'var(--canvas-alt)',
                      border: '1px solid var(--border)',
                      color: 'var(--ink)',
                    }}
                  />
                </div>
              )}
            </div>
          )}

          {/* TAB 3: PASTE TEXT */}
          {activeTab === 'text' && (
            <div className="space-y-3">
              <div>
                <label className="block text-[12px] font-semibold mb-1" style={{ color: 'var(--ink)' }}>
                  Note Title (Optional)
                </label>
                <input
                  type="text"
                  value={pastedTitle}
                  onChange={(e) => setPastedTitle(e.target.value)}
                  placeholder="e.g. Chapter 4 Summary or Reading Notes"
                  disabled={loading}
                  className="w-full px-3 py-2 text-[12px] rounded-lg focus:outline-none transition-colors"
                  style={{
                    background: 'var(--canvas-alt)',
                    border: '1px solid var(--border)',
                    color: 'var(--ink)',
                  }}
                />
              </div>

              <div>
                <label className="block text-[12px] font-semibold mb-1" style={{ color: 'var(--ink)' }}>
                  Study Notes Content *
                </label>
                <textarea
                  rows={6}
                  value={pastedText}
                  onChange={(e) => {
                    setPastedText(e.target.value);
                    if (textError) setTextError(null);
                  }}
                  placeholder="Paste lecture excerpts, textbook passages, or key insights here…"
                  disabled={loading}
                  className="w-full px-3 py-2.5 text-[12px] rounded-lg focus:outline-none resize-none transition-colors"
                  style={{
                    background: 'var(--canvas-alt)',
                    border: `1px solid ${textError ? 'var(--negative)' : 'var(--border)'}`,
                    color: 'var(--ink)',
                  }}
                />
                {textError && (
                  <p className="text-[11px] mt-1" style={{ color: 'var(--negative)' }}>
                    {textError}
                  </p>
                )}
              </div>
            </div>
          )}
        </div>

        {/* Footer Actions */}
        <div
          className="p-4 flex items-center justify-between"
          style={{
            borderTop: '1px solid var(--border)',
            background: 'var(--canvas-alt)',
          }}
        >
          <div className="text-[11px]" style={{ color: 'var(--ink-faint)' }}>
            Grounded in vector semantic indexing
          </div>
          <div className="flex items-center gap-2.5">
            <button
              onClick={onClose}
              disabled={loading}
              className="px-4 py-2 text-[12px] font-medium rounded-lg transition-colors hover:opacity-80"
              style={{
                background: 'var(--surface)',
                border: '1px solid var(--border)',
                color: 'var(--ink-muted)',
              }}
            >
              Cancel
            </button>
            <button
              onClick={() => {
                if (activeTab === 'urls') submitUrls();
                else if (activeTab === 'upload') submitFile();
                else if (activeTab === 'text') submitText();
              }}
              disabled={loading}
              className="px-4 py-2 text-[12px] font-semibold rounded-lg shadow-sm transition-opacity hover:opacity-90 flex items-center gap-2"
              style={{
                background: 'var(--accent)',
                color: 'var(--accent-ink)',
              }}
            >
              {loading && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
              <span>{loading ? 'Indexing…' : 'Add to Notebook'}</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
