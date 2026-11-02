import React, { useEffect, useState } from 'react';
import { Linking, Share, View } from 'react-native';
import { Text } from '../../components/Typography';
import { router, useLocalSearchParams } from 'expo-router';
import { Body, Button, Empty, Label, Page, Section, usePalette } from '../../components/Editorial';
import { useSignal } from '../../hooks/useSignal';
import { headline } from '../../theme';
import type { Explanation } from '../../services/types';
import { PostMedia } from '../../components/PostMedia';

export default function Reader() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const s = useSignal();
  const c = usePalette();
  const post = s.posts.find(p => p.id === id);
  const [explanation, setExplanation] = useState<Explanation | null>(null);
  const [explaining, setExplaining] = useState(false);
  useEffect(() => { setExplanation(null); }, [id]);
  const back = () => router.canGoBack() ? router.back() : router.replace('/');
  if (!post) return <Page><Button label="Back to reader" onPress={back} /><Empty text="Post unavailable. It may have expired; saved posts remain in your library." /></Page>;
  const insight = post.insight;
  async function explain() {
    setExplaining(true);
    try { setExplanation(await s.explain(post!)); } finally { setExplaining(false); }
  }
  return <Page>
    <Button label="Back to your reading" icon="arrow-back" subtle onPress={back} />
    <Label color={c.accent}>{insight.category.toUpperCase()} / {post.generation === 'demo' ? 'SYNTHETIC DEMO' : 'AI-ASSISTED READING'}</Label>
    <Text style={{ color: c.text, fontFamily: headline, fontWeight: '800', fontSize: 38, lineHeight: 46, letterSpacing: -0.8 }}>{insight.title}</Text>
    <View style={{ gap: 7 }}>
      <Text style={{ color: c.text, fontSize: 14 }}>{post.author || 'Author not provided in export'}</Text>
      <Text style={{ color: c.muted, fontSize: 12 }}>{post.published_at ? new Date(post.published_at).toLocaleString() : 'Publication date / timezone not provided'}</Text>
      {post.author_url && <Button label="Author profile" subtle onPress={() => void s.run(() => Linking.openURL(post.author_url!))} />}
    </View>
    <PostMedia post={post} expanded />
    <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 8 }}>
      <Button label={post.saved ? 'Saved' : 'Save'} icon={post.saved ? 'bookmark' : 'bookmark-outline'} onPress={() => void s.run(() => s.save(post))} />
      <Button label={post.read ? 'Mark unread' : 'Mark read'} icon="checkmark" subtle onPress={() => void s.run(() => s.markRead(post))} />
      <Button label="Share" icon="share-outline" subtle onPress={() => void s.run(() => Share.share({
        message: `${insight.title}\n\nAI-generated summary: ${insight.summary}\n\n${post.url || 'Source URL unavailable. Shared from SIGNAL.'}`,
      }))} />
    </View>
    <View style={{ backgroundColor: c.accentBg, borderRadius: 28, padding: 24, gap: 16 }}>
      <Label color={c.accentOnTint}>THE SIGNAL / AI-GENERATED SUMMARY</Label><Body>{insight.summary}</Body>
      <Text style={{ color: c.muted, fontSize: 11 }}>Relevance {insight.relevance_score}/100 · Technical depth {insight.depth_score}/100</Text>
    </View>
    <Section title="THE ORIGINAL POST" detail="Author's text · unedited" />
    <Body>{post.original_text}</Body>
    {post.url ? <Button label="Read original on LinkedIn" icon="open-outline" subtle
      onPress={() => void s.run(() => Linking.openURL(post.url!))} /> : <Body muted>Original LinkedIn URL not provided.</Body>}
    <View style={{ height: 1, backgroundColor: c.line }} />
    <Label color={c.accent}>AI INTERPRETATION / NOT THE AUTHOR'S WORDS</Label>
    {[
      ['The key insight', insight.main_insight], ['Architecture patterns', insight.patterns.join('\n\n') || 'No architecture pattern identified.'],
      ['Technologies mentioned', insight.technologies.join(' · ') || 'No named technologies.'],
      ['Put it into practice', insight.practical_relevance], ['Why this matters', insight.why_it_matters],
    ].map(([title, text]) => <View key={title} style={{ gap: 12 }}>
      <Text style={{ fontFamily: headline, fontWeight: '700', fontSize: 25, color: c.text }}>{title}</Text><Body>{text}</Body>
    </View>)}
    <Text style={{ color: c.accent, fontSize: 12 }}>{insight.tags.map(t => `#${t}`).join('  ')}</Text>
    <Button label={explaining ? 'Thinking…' : 'Explain this to me'} icon="sparkles-outline" disabled={explaining}
      onPress={() => void s.run(explain)} />
    {explanation && <View style={{ padding: 24, borderRadius: 28, backgroundColor: c.surface, gap: 24 }}>
      <Label color={c.accent}>AI-GENERATED EXPLANATIONS</Label>
      {[
        ['Executive overview', explanation.executive], ['Solution architect', explanation.architect], ['Deep technical', explanation.technical],
      ].map(([title, text]) => <View key={title} style={{ gap: 10 }}>
        <Text style={{ fontFamily: headline, fontWeight: '700', color: c.text, fontSize: 23 }}>{title}</Text><Body>{text}</Body>
      </View>)}
    </View>}
    <Body muted>Generated insights can be incomplete or incorrect. Check the original before making technical decisions.</Body>
  </Page>;
}
