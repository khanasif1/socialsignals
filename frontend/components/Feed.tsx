import React, { useEffect, useState } from 'react';
import { View } from 'react-native';
import { Searchbar } from 'react-native-paper';
import { Text } from './Typography';
import { bodyFont } from '../theme';
import { Button, Chips, Empty, Heading, Page, PostCard, usePalette } from './Editorial';
import { useSignal } from '../hooks/useSignal';
import { filterPosts } from '../services/reading';

export function Feed({ saved = false, initialTopic = '' }: { saved?: boolean; initialTopic?: string }) {
  const s = useSignal();
  const c = usePalette();
  const [query, setQuery] = useState('');
  const [topic, setTopic] = useState(initialTopic);
  const [category, setCategory] = useState('');
  const [sort, setSort] = useState('recency');
  const [days, setDays] = useState('Any date');
  const [unread, setUnread] = useState(false);
  const [limit, setLimit] = useState(20);
  useEffect(() => { setLimit(20); }, [query, topic, category, sort, days, unread]);
  const posts = s.posts.filter(p => !saved || p.saved);
  const result = filterPosts(posts, { query, topic, category, sort, unread,
    days: days === 'Any date' ? undefined : Number(days.split(' ')[0]) });
  return <Page>
    <Heading title={saved ? 'Your library.' : 'Follow the signal.'} subtitle={saved
      ? 'Ideas worth keeping. A library that stays yours.' : 'Technical thinking, without the endless scroll.'} />
    <Searchbar value={query} onChangeText={setQuery} placeholder="Search ideas, authors, technologies…"
      accessibilityLabel="Search posts" placeholderTextColor={c.muted} autoCapitalize="none"
      iconColor={c.accent} inputStyle={{ fontFamily: bodyFont, color: c.ink, fontSize: 14 }}
      style={{ backgroundColor: c.raised, borderRadius: 28 }} />
    <View style={{ gap: 5, marginTop: -8 }}>
      <Chips items={['All topics', ...new Set(posts.flatMap(p => p.insight.topics))]} selected={topic || 'All topics'}
        onSelect={value => setTopic(value === 'All topics' ? '' : value)} />
      <Chips items={['All categories', ...new Set(posts.map(p => p.insight.category))]} selected={category || 'All categories'}
        onSelect={value => setCategory(value === 'All categories' ? '' : value)} />
      <Chips items={['Any date', '1 day', '3 days', '7 days', '30 days']} selected={days} onSelect={setDays} />
      <Chips items={['Latest', 'Most relevant', 'Unread']} selected={unread ? 'Unread' : sort === 'recency' ? 'Latest' : 'Most relevant'}
        onSelect={value => { setUnread(value === 'Unread'); setSort(value === 'Most relevant' ? 'relevance' : 'recency'); }} />
    </View>
    <Text style={{ color: c.muted, fontSize: 11 }}>{result.length} {result.length === 1 ? 'insight' : 'insights'}{saved ? ' · Saved content survives feed cleanup' : ''}</Text>
    {result.slice(0, limit).map((post, index) => <PostCard key={post.id} post={post} index={index} />)}
    {result.length > limit && <Button label={`Load more (${result.length - limit} remaining)`} subtle onPress={() => setLimit(value => value + 20)} />}
    {!result.length && <Empty text={saved ? 'Your saved ideas will live here. Bookmark a post to keep it beyond feed retention.' : 'No matching posts. Adjust your filters or import a LinkedIn export.'} />}
  </Page>;
}
