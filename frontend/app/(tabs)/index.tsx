import React, { useState } from 'react';
import { Pressable, useWindowDimensions, View } from 'react-native';
import { MaterialCommunityIcons } from '@expo/vector-icons';
import { Surface } from 'react-native-paper';
import { router } from 'expo-router';
import { Button, Chips, Empty, Heading, Label, Page, PostCard, Section, TopicPill, usePalette } from '../../components/Editorial';
import { Text } from '../../components/Typography';
import { useSignal } from '../../hooks/useSignal';
import { filterPosts, topicGroups } from '../../services/reading';

export default function Today() {
  const s = useSignal();
  const c = usePalette();
  const wide = useWindowDimensions().width >= 900;
  const [view, setView] = useState('For you');
  const ranked = filterPosts(s.posts, { sort: 'relevance' });
  const recent = filterPosts(s.posts, {});
  const preferred = new Set(s.preferences.preferred_topics);
  const recommended = ranked.filter(p => !p.read).sort((a, b) =>
    b.insight.topics.filter(t => preferred.has(t)).length - a.insight.topics.filter(t => preferred.has(t)).length);
  const stream = view === 'Latest' ? recent : view === 'Saved' ? ranked.filter(post => post.saved)
    : [...recommended, ...ranked.filter(post => post.read)];
  const visible = stream.filter(post => post.id !== ranked[0]?.id || view === 'Saved');
  const saved = s.posts.filter(post => post.saved).length;
  return <Page syncAction>
    <View style={{ gap: 12 }}>
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 7 }}>
        <MaterialCommunityIcons name="white-balance-sunny" size={16} color={c.accent} />
        <Label>{new Date().toLocaleDateString(undefined, { weekday: 'long', month: 'long', day: 'numeric' })}</Label>
      </View>
      <Heading title="Less noise. More signal." subtitle="A little inspiration. A deeper understanding. Your own space to connect the dots." />
    </View>
    <View style={{ flexDirection: wide ? 'row' : 'column', gap: 20 }}>
      <View style={{ flex: wide ? 2 : undefined, minWidth: 0 }}>
        {ranked[0] ? <PostCard post={ranked[0]} featured /> : <Empty />}
      </View>
      <View style={{ flex: wide ? 1 : undefined, minWidth: wide ? 280 : undefined, gap: 16 }}>
        <View style={{ flexDirection: 'row', gap: 14 }}>
          <Surface elevation={0} style={{ flex: 1, backgroundColor: c.secondaryContainer, borderRadius: 28, padding: 20, gap: 12 }}>
            <MaterialCommunityIcons name="lightbulb-on-outline" size={26} color={c.onSecondaryContainer} />
            <Text style={{ color: c.onSecondaryContainer, fontSize: 38, fontFamily: 'SignalDisplay' }}>{s.posts.filter(post => !post.read).length.toString().padStart(2, '0')}</Text>
            <Text style={{ color: c.onSecondaryContainer, fontSize: 12 }}>Unread ideas</Text>
          </Surface>
          <Surface elevation={0} style={{ flex: 1, backgroundColor: c.tertiaryContainer, borderRadius: 28, padding: 20, gap: 12 }}>
            <MaterialCommunityIcons name="bookmark-multiple-outline" size={26} color={c.onTertiaryContainer} />
            <Text style={{ color: c.onTertiaryContainer, fontSize: 38, fontFamily: 'SignalDisplay' }}>{String(saved).padStart(2, '0')}</Text>
            <Text style={{ color: c.onTertiaryContainer, fontSize: 12 }}>Saved for later</Text>
          </Surface>
        </View>
        <Surface elevation={1} style={{ flex: 1, backgroundColor: c.surface, borderRadius: 28, padding: 22, gap: 15 }}>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 9 }}>
            <MaterialCommunityIcons name="headphones" size={23} color={c.accent} />
            <Text style={{ color: c.text, fontSize: 18, fontWeight: '700' }}>Your space. Your pace.</Text>
          </View>
          <Text style={{ color: c.muted, fontSize: 13, lineHeight: 21 }}>Good ideas don't expire in your library. Keep the ones that stay with you.</Text>
          <Button label="Open your library" icon="arrow-forward" subtle onPress={() => router.push('/saved')} />
        </Surface>
      </View>
    </View>
    <View style={{ flexDirection: wide ? 'row' : 'column', gap: 24 }}>
      <View style={{ flex: wide ? 2 : undefined, minWidth: 0, gap: 18 }}>
        <Section title="A fresh perspective" detail={`${stream.length} insights`} />
        <Chips items={['For you', 'Latest', 'Saved']} selected={view} onSelect={setView} />
        {visible.slice(0, 6).map((post, index) => <PostCard key={post.id} post={post} index={index} />)}
        {!visible.length && <Empty text={view === 'Saved' ? 'Bookmark an insight to start your personal collection.' : 'You are all caught up. Explore your collection or import more posts.'} />}
        <Button label="Explore all insights" icon="arrow-forward" subtle onPress={() => router.push('/discover')} />
      </View>
      <View style={{ flex: wide ? 1 : undefined, minWidth: wide ? 280 : undefined, gap: 22 }}>
        <Surface elevation={0} style={{ backgroundColor: c.raised, padding: 24, borderRadius: 28, gap: 18 }}>
          <View style={{ flexDirection: 'row', gap: 8, alignItems: 'center' }}>
            <MaterialCommunityIcons name="radar" size={24} color={c.accentOnTint} />
            <Text style={{ color: c.accentOnTint, fontSize: 20, fontWeight: '700' }}>In your orbit</Text>
          </View>
          <Text style={{ color: c.muted, fontSize: 13, lineHeight: 21 }}>Follow a thread. See where it takes you.</Text>
          <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 9 }}>
            {topicGroups(s.posts).slice(0, 6).map(({ name, posts }) => <TopicPill key={name} name={name} count={posts.length} />)}
          </View>
        </Surface>
        <Surface elevation={1} style={{ backgroundColor: c.surface, padding: 24, borderRadius: 28, gap: 16 }}>
          <Section title="Up next" detail="Unread" />
          {recommended.slice(0, 3).map(post => <Pressable key={post.id} accessibilityRole="button"
            accessibilityLabel={`Read ${post.insight.title}`} onPress={() => router.push(`/post/${post.id}`)}
            style={{ borderTopWidth: 1, borderColor: c.line, paddingTop: 16, gap: 8 }}>
            <Label>{post.insight.category}</Label>
            <Text style={{ color: c.text, fontSize: 15, fontWeight: '700', lineHeight: 23 }}>{post.insight.title}</Text>
            <MaterialCommunityIcons name="arrow-top-right" size={19} color={c.accent} />
          </Pressable>)}
          {!recommended.length && <Text style={{ color: c.muted, fontSize: 13 }}>All read. Your next discovery is a search away.</Text>}
        </Surface>
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 7, padding: 8 }}>
          <MaterialCommunityIcons name="shield-lock-outline" color={c.muted} size={16} />
          <Text style={{ color: c.muted, fontSize: 11, flex: 1 }}>{s.demo ? 'Fictional demo edition · Your live data stays separate' : 'Private by design · Your LinkedIn sources'}</Text>
        </View>
      </View>
    </View>
    <View style={{ paddingTop: 8 }}>
      <Text style={{ color: c.muted, fontSize: 11 }}>Last sync: {s.syncStatus.finished_at ? new Date(s.syncStatus.finished_at).toLocaleString() : 'No live sync yet'}</Text>
    </View>
  </Page>;
}
