export interface User {
  id: string;
  _id?: string;
  name: string;
  email: string;
  created_at: string;
  is_active: boolean;
}

export interface Project {
  id: string;
  _id?: string;
  user_id: string;
  name: string;
  description: string;
  index_id: string;
  created_at: string;
  updated_at: string;
  source_count?: number;
  conversation_count?: number;
}

export interface Conversation {
  id: string;
  _id?: string;
  user_id: string;
  project_id: string;
  title: string;
  status: 'active' | 'archived';
  created_at: string;
  updated_at: string;
  last_message_at: string;
  message_count?: number;
}

export interface SourceInfo {
  source_id: string;
  url: string;
  original_url?: string;
  resolved_url?: string | null;
  title: string;
  source_type?: 'website' | 'pdf' | 'file' | 'text' | string;
  status: 'success' | 'failed';
  chunk_count: number;
  chunks_indexed?: number;
  char_count: number;
  truncated?: boolean;
  error?: string | null;
}


export interface IngestResponse {
  session_id: string;
  topic_name: string;
  total_sources?: number;
  successful_sources?: number;
  failed_sources?: number;
  total_chunks_indexed?: number;
  total_submitted: number;
  successful_count: number;
  failed_count: number;
  total_chunks: number;
  sources: SourceInfo[];
  results?: SourceInfo[];
}

export interface ChunkInfo {
  source_id: string;
  url: string;
  title: string;
  text: string;
  score: number;
}

export interface ClassificationResult {
  classification: 'agree' | 'partial' | 'conflict';
  confidence: number;
  reasoning: string;
  key_differences: string;
}

export interface SourceSummary {
  source_id: string;
  url: string;
  title: string;
  summary: string;
}

export interface ChatResponse {
  answer: string;
  classification: ClassificationResult;
  source_summaries: SourceSummary[];
  retrieved_chunks: Record<string, ChunkInfo[]>;
  session_id: string;
  question: string;
}

export interface RetrievalMetadata {
  retrieval_mode: 'vector' | 'hybrid' | string;
  vector_results_count: number;
  graph_results_count: number;
  final_context_count: number;
  graph_entity_ids?: string[];
  graph_relationship_ids?: string[];
  source_ids?: string[];
  chunk_ids?: string[];
}

export interface Message {
  id: string;
  _id?: string;
  user_id?: string;
  project_id?: string;
  conversation_id?: string;
  role: 'user' | 'assistant';
  content: string;
  chatResponse?: ChatResponse;
  classification?: ClassificationResult;
  source_summaries?: SourceSummary[];
  retrieved_chunks?: Record<string, ChunkInfo[]>;
  retrieval_metadata?: RetrievalMetadata;
  created_at?: string;
  timestamp?: Date;
}

export interface PaginatedMessages {
  messages: Message[];
  total: number;
  conversation_id: string;
}

export type StudioToolType = 'summary' | 'flashcards' | 'quiz' | 'mindmap' | 'notes' | 'datatable';

export interface StudioFlashcard {
  id: number;
  category?: string;
  front: string;
  back: string;
  source?: string;
}

export interface StudioQuizQuestion {
  id: number;
  question: string;
  options: string[];
  answer_index: number;
  explanation: string;
}

export interface StudioMindmapNode {
  name: string;
  detail?: string;
  children?: StudioMindmapNode[];
}

export interface StudioDataTable {
  title?: string;
  description?: string;
  columns: string[];
  rows: string[][];
}

export interface StudioNotes {
  title?: string;
  markdown_content: string;
}

export interface StudioSummary {
  title?: string;
  overview: string;
  key_takeaways: string[];
  source_breakdown: Array<{ source_id: string; main_contribution: string }>;
}

