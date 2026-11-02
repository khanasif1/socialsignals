import type { Post } from './types';

export function readingMinutes(post: Post): number {
  return Math.max(1, Math.ceil(post.original_text.split(/\s+/).length / 220));
}
export function filterPosts(posts: Post[], options: {
  query?: string; topic?: string; category?: string; days?: number; sort?: string; unread?: boolean;
}): Post[] {
  const q = (options.query || '').toLocaleLowerCase();
  return posts.filter(p =>
    (!q || `${p.insight.title} ${p.insight.summary} ${p.original_text} ${p.author || ''}`.toLocaleLowerCase().includes(q))
    && (!options.topic || p.insight.topics.includes(options.topic))
    && (!options.category || p.insight.category === options.category)
    && (!options.unread || !p.read)
    && (!options.days || (!!p.published_at && Date.parse(p.published_at) >= Date.now() - options.days * 86400000))
  ).sort((a, b) => options.sort === 'relevance'
    ? b.insight.relevance_score - a.insight.relevance_score
    : Date.parse(b.published_at || b.imported_at) - Date.parse(a.published_at || a.imported_at));
}
export function topicGroups(posts: Post[]) {
  const names = [...new Set(posts.flatMap(p => p.insight.topics))];
  return names.map(name => ({
    name, posts: posts.filter(p => p.insight.topics.includes(name))
      .sort((a, b) => b.insight.relevance_score - a.insight.relevance_score),
  })).sort((a, b) => b.posts.length - a.posts.length);
}
