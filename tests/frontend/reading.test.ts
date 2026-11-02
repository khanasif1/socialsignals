import { strict as assert } from 'node:assert';
import { test } from 'node:test';
import samples from '../../frontend/assets/posts.json';
import { filterPosts, readingMinutes, topicGroups } from '../../frontend/services/reading';
import type { Post } from '../../frontend/services/types';

const posts = samples as Post[];
test('search includes source text, summaries and authors', () => {
  assert.equal(filterPosts(posts, { query: 'Maya Patel' }).length, 1);
  assert.equal(filterPosts(posts, { query: 'idempotent' }).length, 1);
  assert.equal(filterPosts(posts, { query: 'no-such-topic' }).length, 0);
});
test('topic, category, unread filters and relevance sorting compose', () => {
  const result = filterPosts(posts, { topic: 'Agentic AI', unread: true, sort: 'relevance' });
  assert.equal(result.length, 1);
  assert.equal(result[0]?.id, 'demo-context');
  assert.equal(filterPosts(posts, { category: 'AI Security' })[0]?.id, 'demo-mcp');
  assert.equal(filterPosts(posts, { sort: 'relevance' })[0]?.insight.relevance_score, 98);
});
test('date filtering excludes missing and old dates', () => {
  const fresh = { ...posts[0]!, published_at: new Date().toISOString() };
  assert.equal(filterPosts([fresh, { ...fresh, published_at: null }], { days: 1 }).length, 1);
});
test('topic counts, reading time and fixtures remain honest', () => {
  assert.equal(topicGroups(posts).find(t => t.name === 'Agentic AI')?.posts.length, 2);
  assert.ok(posts.every(p => readingMinutes(p) >= 1));
  assert.ok(posts.every(p => p.generation === 'demo' && p.url === null && p.original_text.includes('SYNTHETIC')));
  const before = posts.map(p => p.id);
  filterPosts(posts, { sort: 'relevance' });
  assert.deepEqual(posts.map(p => p.id), before);
});
