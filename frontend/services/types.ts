export type Insight = {
  title: string; category: string; topics: string[]; summary: string; main_insight: string;
  patterns: string[]; technologies: string[]; practical_relevance: string; why_it_matters: string;
  depth_score: number; relevance_score: number; tags: string[];
};
export type Post = {
  id: string; author: string | null; author_url: string | null; url: string | null;
  published_at: string | null; original_text: string; imported_at: string;
  image_urls?: string[];
  source: 'linkedin_export' | 'linkedin_crawler'; insight: Insight; generation: 'llm' | 'demo'; read: boolean; saved: boolean;
};
export type Preferences = {
  retention_days: 1 | 3 | 7 | 14 | 30; max_posts_per_sync: number; min_relevance_score: number;
  summary_length: 'short' | 'medium' | 'long'; preferred_topics: string[];
  sync_frequency: 'manual' | 'hourly' | 'daily'; theme: 'dark' | 'light'; font_size: 'standard' | 'large';
};
export type SyncStatus = {
  status: 'never' | 'running' | 'completed' | 'failed'; started_at: string | null;
  finished_at: string | null; imported: number; relevant: number; duplicates: number;
  remaining: number; message: string;
};
export type Integration = {
  connected: boolean; oauth_available: boolean; personal_feed_available: false; mode: 'export' | 'crawler'; message: string;
  crawler?: {
    enabled: boolean; status: 'never' | 'disabled' | 'running' | 'completed' | 'failed' | 'action_required';
    started_at: string | null; finished_at: string | null; last_success_at: string | null;
    extracted: number; skipped: number; limit_reached: boolean; code: string; message: string;
  };
};
export type Explanation = { executive: string; architect: string; technical: string; generated: boolean };
export type Statistics = {
  total_posts: number; relevant_posts: number; unread_posts: number;
  by_topic: Record<string, number>; by_author: Record<string, number>; latest_sync: SyncStatus;
};
