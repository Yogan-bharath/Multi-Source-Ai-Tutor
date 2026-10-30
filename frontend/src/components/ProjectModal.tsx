'use client';
import React, { useState } from 'react';
import { FolderPlus, X, Loader2, AlertCircle } from 'lucide-react';
import type { Project } from '@/types';

interface ProjectModalProps {
  isOpen: boolean;
  onClose: () => void;
  onProjectCreated: (project: Project) => void;
}

export function ProjectModal({ isOpen, onClose, onProjectCreated }: ProjectModalProps) {
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) {
      setError('Please provide a notebook name.');
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const res = await fetch('/api/projects', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({
          name: name.trim(),
          description: description.trim(),
        }),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: 'Failed to create notebook' }));
        throw new Error(err.detail || 'Could not create notebook');
      }

      const created: Project = await res.json();
      setName('');
      setDescription('');
      onProjectCreated(created);
      onClose();
    } catch (err: any) {
      setError(err.message || 'Error creating notebook');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 animate-fadeIn"
      style={{ background: 'rgba(0, 0, 0, 0.65)', backdropFilter: 'blur(4px)' }}
      onClick={onClose}
    >
      <div
        className="rounded-2xl shadow-modal w-full max-w-md overflow-hidden relative animate-scaleIn"
        style={{
          background: 'var(--surface-overlay)',
          border: '1px solid var(--border)',
          color: 'var(--ink)',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <button
          onClick={onClose}
          className="absolute top-4 right-4 p-1.5 rounded-lg transition-colors hover:opacity-80"
          style={{ color: 'var(--ink-faint)' }}
          title="Close dialog"
        >
          <X className="w-4 h-4" />
        </button>

        <div className="p-6">
          <div className="flex items-center gap-3 mb-5">
            <div
              className="w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0"
              style={{
                background: 'var(--accent-muted)',
                color: 'var(--accent)',
                border: '1px solid var(--accent)',
              }}
            >
              <FolderPlus className="w-5 h-5" />
            </div>
            <div>
              <h3 className="font-bold text-[16px] leading-snug" style={{ color: 'var(--ink)' }}>
                Create Research Notebook
              </h3>
              <p className="text-[12px] mt-0.5" style={{ color: 'var(--ink-muted)' }}>
                Curate sources and ground discussions in one place
              </p>
            </div>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            {error && (
              <div
                className="p-3 rounded-lg flex items-center gap-2 text-[12px]"
                style={{
                  background: 'var(--negative-muted)',
                  border: '1px solid var(--negative)',
                  color: 'var(--negative)',
                }}
              >
                <AlertCircle className="w-4 h-4 flex-shrink-0" />
                <span>{error}</span>
              </div>
            )}

            <div>
              <label className="block text-[12px] font-semibold mb-1.5" style={{ color: 'var(--ink)' }}>
                Notebook Title *
              </label>
              <input
                type="text"
                required
                placeholder="e.g. Quantum Computing or Deep Learning"
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="w-full px-3.5 py-2.5 text-[13px] rounded-lg focus:outline-none transition-colors"
                style={{
                  background: 'var(--canvas-alt)',
                  border: '1px solid var(--border)',
                  color: 'var(--ink)',
                }}
              />
            </div>

            <div>
              <label className="block text-[12px] font-semibold mb-1.5" style={{ color: 'var(--ink)' }}>
                Description (Optional)
              </label>
              <textarea
                rows={3}
                placeholder="What are your goals or focus topics for this workspace?"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                className="w-full px-3.5 py-2.5 text-[13px] rounded-lg focus:outline-none resize-none transition-colors"
                style={{
                  background: 'var(--canvas-alt)',
                  border: '1px solid var(--border)',
                  color: 'var(--ink)',
                }}
              />
            </div>

            <div
              className="flex items-center justify-end gap-2.5 pt-4"
              style={{ borderTop: '1px solid var(--border-muted)' }}
            >
              <button
                type="button"
                onClick={onClose}
                className="px-4 py-2 text-[13px] font-medium rounded-lg transition-colors hover:opacity-85"
                style={{
                  background: 'var(--canvas-alt)',
                  border: '1px solid var(--border)',
                  color: 'var(--ink-muted)',
                }}
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={loading}
                className="px-4 py-2 text-[13px] font-semibold rounded-lg shadow-sm transition-opacity hover:opacity-90 flex items-center gap-2"
                style={{
                  background: 'var(--accent)',
                  color: 'var(--accent-ink)',
                }}
              >
                {loading && <Loader2 className="w-4 h-4 animate-spin" />}
                <span>Create Notebook</span>
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}
