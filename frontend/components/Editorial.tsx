import React from 'react';
import { Pressable, RefreshControl, ScrollView, useWindowDimensions, View } from 'react-native';
import { Ionicons, MaterialCommunityIcons } from '@expo/vector-icons';
import { Avatar, Button as MaterialButton, Card, Chip, FAB, IconButton, Surface } from 'react-native-paper';
import { router, usePathname } from 'expo-router';
import Animated, { FadeInDown, useReducedMotion } from 'react-native-reanimated';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { useSignal } from '../hooks/useSignal';
import { dark, headline, light } from '../theme';
import type { Post } from '../services/types';
import { readingMinutes } from '../services/reading';
import { Text } from './Typography';
import { PostMedia } from './PostMedia';

export function usePalette() {
  return useSignal().preferences.theme === 'light' ? light : dark;
}
export function Label({ children, color }: { children: React.ReactNode; color?: string }) {
  const c = usePalette();
  return <Text style={{ color: color || c.muted, fontSize: 13, lineHeight: 18 }}>{children}</Text>;
}
export function Body({ children, muted = false }: { children: React.ReactNode; muted?: boolean }) {
  const c = usePalette();
  const large = useSignal().preferences.font_size === 'large';
  return <Text style={{ color: muted ? c.muted : c.ink, fontSize: large ? 19 : 16, lineHeight: large ? 31 : 26 }}>{children}</Text>;
}
export function Button({ label, onPress, icon, subtle = false, disabled = false }: {
  label: string; onPress: () => void; icon?: keyof typeof Ionicons.glyphMap; subtle?: boolean; disabled?: boolean;
}) {
  const c = usePalette();
  return <MaterialButton accessibilityLabel={label} disabled={disabled} onPress={onPress}
    mode={subtle ? 'outlined' : 'contained'} buttonColor={subtle ? undefined : c.button}
    textColor={subtle ? c.accent : c.buttonText} style={{ borderRadius: 28 }}
    contentStyle={{ minHeight: 48, paddingVertical: 3 }}
    labelStyle={{ fontFamily: 'SignalBold', fontSize: 13, flexShrink: 1 }}
    icon={icon ? ({ color, size }) => <Ionicons name={icon} size={size} color={color} /> : undefined}>
    {label}
  </MaterialButton>;
}
export function Chips({ items, selected, onSelect }: { items: string[]; selected?: string; onSelect: (item: string) => void }) {
  const c = usePalette();
  return <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 8, paddingVertical: 6 }}>
    {items.map(item => <Chip key={item} accessibilityRole="button" accessibilityLabel={item}
      accessibilityState={{ selected: selected === item }} selected={selected === item} showSelectedCheck
      mode={selected === item ? 'flat' : 'outlined'} onPress={() => onSelect(item)}
      style={{ minHeight: 44, justifyContent: 'center', backgroundColor: selected === item ? c.accentBg : c.surface, borderRadius: 14 }}
      textStyle={{ fontFamily: selected === item ? 'SignalBold' : 'SignalRegular', fontSize: 12,
        color: selected === item ? c.accentOnTint : c.muted }}>{item}</Chip>)}
  </ScrollView>;
}
export function Page({ children, syncAction = false }: { children: React.ReactNode; syncAction?: boolean }) {
  const c = usePalette();
  const signal = useSignal();
  const insets = useSafeAreaInsets();
  const wide = useWindowDimensions().width >= 900;
  const pathname = usePathname();
  const links = [
    { title: 'Today', path: '/' }, { title: 'Discover', path: '/discover' },
    { title: 'Topics', path: '/topics' }, { title: 'Saved', path: '/saved' }, { title: 'Settings', path: '/settings' },
  ] as const;
  return <View style={{ flex: 1, backgroundColor: c.bg }}>
    <Surface elevation={0} style={{ backgroundColor: c.bg, paddingTop: insets.top + 10, paddingBottom: 10, paddingHorizontal: wide ? 32 : 20 }}>
      <View style={{ width: '100%', maxWidth: 1180, minHeight: 52, alignSelf: 'center', flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', gap: 18 }}>
        <Pressable accessibilityRole="button" accessibilityLabel="SIGNAL home" onPress={() => router.push('/')}
          style={{ minHeight: 48, flexDirection: 'row', alignItems: 'center', gap: 9 }}>
          <View style={{ backgroundColor: c.accentBg, borderRadius: 15, padding: 9 }}>
            <MaterialCommunityIcons name="waveform" color={c.accent} size={24} />
          </View>
          <Text style={{ color: c.accent, fontFamily: headline, fontSize: 24, letterSpacing: -1 }}>signal<Text style={{ color: c.ink }}>.</Text></Text>
        </Pressable>
        {wide && <View style={{ flexDirection: 'row', alignItems: 'center', gap: 4 }}>
          {links.map(link => <MaterialButton key={link.path} accessibilityLabel={link.title}
            accessibilityState={{ selected: pathname === link.path }} onPress={() => router.push(link.path)}
            mode={pathname === link.path ? 'contained-tonal' : 'text'}
            textColor={pathname === link.path ? c.accentOnTint : c.muted}
            contentStyle={{ minHeight: 44 }} style={{ borderRadius: 24 }}>{link.title}</MaterialButton>)}
        </View>}
        <View style={{ flexDirection: 'row', gap: 4, alignItems: 'center' }}>
          {wide && <View style={{ flexDirection: 'row', alignItems: 'center', gap: 5, marginRight: 8 }}>
            <MaterialCommunityIcons name="shield-lock-outline" color={c.muted} size={16} />
            <Text style={{ color: c.muted, fontSize: 11 }}>{signal.demo ? 'Demo space' : 'Private space'}</Text>
          </View>}
          <IconButton icon="magnify" accessibilityLabel="Search insights" onPress={() => router.push('/discover')}
            iconColor={c.accent} mode="contained-tonal" size={22} />
        </View>
      </View>
    </Surface>
    <ScrollView keyboardShouldPersistTaps="handled" contentContainerStyle={{
      paddingTop: wide ? 28 : 18, paddingBottom: syncAction ? 110 : 40, paddingHorizontal: wide ? 32 : 20,
      width: '100%', maxWidth: 1244, alignSelf: 'center', gap: 24,
    }} refreshControl={<RefreshControl refreshing={signal.loading} tintColor={c.accent} onRefresh={() => void signal.run(signal.refresh)} />}>
      {(signal.error || signal.notice) && <Pressable accessibilityRole="button" accessibilityLabel="Dismiss notification" onPress={signal.dismiss}
        style={{ backgroundColor: c.accentBg, borderColor: signal.error ? c.danger : c.line, borderWidth: 1, borderRadius: 20, padding: 16 }}>
        <Text style={{ color: signal.error ? c.danger : c.accent, lineHeight: 21 }}>{signal.error || signal.notice}  ×</Text>
      </Pressable>}
      {!signal.demo && !signal.token && <View style={{ padding: 20, borderRadius: 24, backgroundColor: c.accentBg, gap: 12 }}>
        <Body>Connect your private backend in Settings to start reading.</Body>
        <Button label="Open settings" onPress={() => router.push('/settings')} />
      </View>}
      {children}
      {signal.demo && <Text style={{ color: c.muted, fontSize: 11, lineHeight: 18 }}>DEMO CONTENT · All names and posts in this edition are fictional. No LinkedIn feed is connected.</Text>}
    </ScrollView>
    {syncAction && <FAB icon="sync" label={wide ? 'Sync reader' : undefined}
      accessibilityLabel="Sync LinkedIn exports" loading={signal.syncStatus.status === 'running'}
      disabled={signal.syncStatus.status === 'running'} onPress={() => void signal.run(signal.sync)}
      color={c.buttonText} style={{ position: 'absolute', right: wide ? 32 : 20, bottom: 20,
        borderRadius: 20, backgroundColor: c.button }} />}
  </View>;
}
export function Heading({ title, subtitle }: { title: string; subtitle: string }) {
  const c = usePalette();
  const wide = useWindowDimensions().width >= 900;
  return <View style={{ gap: 10 }}>
    <Text style={{ fontFamily: headline, fontSize: wide ? 40 : 32, color: c.accent, letterSpacing: -1.4 }}>{title}</Text>
    <Text style={{ color: c.muted, fontSize: 14, lineHeight: 22, maxWidth: 620 }}>{subtitle}</Text>
  </View>;
}
export function Section({ title, detail }: { title: string; detail?: string }) {
  const c = usePalette();
  return <View style={{ paddingTop: 5, flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', gap: 8 }}>
    <Text style={{ flex: 1, color: c.text, fontSize: 20, fontWeight: '700', letterSpacing: -0.5 }}>{title}</Text>
    {detail && <Text style={{ color: c.muted, fontSize: 11 }}>{detail}</Text>}
  </View>;
}
function SignalMotif() {
  const c = usePalette();
  return <View pointerEvents="none" accessibilityElementsHidden importantForAccessibility="no-hide-descendants"
    style={{ position: 'absolute', width: 230, height: 230, right: -45, top: -60, opacity: 0.13, alignItems: 'center', justifyContent: 'center' }}>
    {[0, 45, 90, 135].map(angle => <View key={angle} style={{ position: 'absolute', height: 210, width: 95,
      borderRadius: 90, borderWidth: 18, borderColor: c.onHero, transform: [{ rotate: `${angle}deg` }] }} />)}
  </View>;
}
export function TopicIcon({ name, size = 22 }: { name: string; size?: number }) {
  const c = usePalette();
  const value = name.toLowerCase();
  const icon = /security|trust/.test(value) ? 'shield-check-outline'
    : /rag|retrieval/.test(value) ? 'database-search-outline'
    : /mcp|tool/.test(value) ? 'connection'
    : /agent/.test(value) ? 'robot-outline' : 'creation-outline';
  return <MaterialCommunityIcons name={icon} size={size} color={c.accent} />;
}
export function TopicPill({ name, count }: { name: string; count: number }) {
  const c = usePalette();
  return <Chip icon={() => <TopicIcon name={name} size={17} />} mode="outlined"
    accessibilityLabel={`Explore ${name}`} onPress={() => router.push({ pathname: '/discover', params: { topic: name } })}
    style={{ backgroundColor: c.surface, borderColor: c.line, borderRadius: 16, minHeight: 44, justifyContent: 'center' }}
    textStyle={{ fontFamily: 'SignalMedium', color: c.ink, fontSize: 12 }}>
    {name} · {count}
  </Chip>;
}
export function Empty({ text = 'Nothing here yet. Import your LinkedIn export from Settings.' }: { text?: string }) {
  const c = usePalette();
  return <View style={{ padding: 28, gap: 12, alignItems: 'center', backgroundColor: c.surface, borderRadius: 16 }}>
    <Ionicons name="planet-outline" color={c.accent} size={30} /><Body muted>{text}</Body>
  </View>;
}
export function PostCard({ post, featured = false, index = 0 }: { post: Post; featured?: boolean; index?: number }) {
  const c = usePalette();
  const signal = useSignal();
  const reduced = useReducedMotion();
  const large = signal.preferences.font_size === 'large';
  const accent = c.accent;
  const date = post.published_at ? new Date(post.published_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric' }) : 'Date unavailable';
  const save = () => void signal.run(() => signal.save(post));
  const open = () => router.push(`/post/${post.id}`);
  const initials = (post.author || '?').split(' ').map(word => word[0]).slice(0, 2).join('');
  if (featured) return <Animated.View entering={reduced ? undefined : FadeInDown.duration(350)}>
    <Card mode="contained" style={{ backgroundColor: c.hero, borderRadius: 32, overflow: 'hidden' }}>
      <SignalMotif />
      <Card.Content style={{ padding: 24, gap: 20 }}>
        <View style={{ flexDirection: 'row', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'space-between', gap: 12 }}>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
            <MaterialCommunityIcons name="creation" size={20} color={c.onHero} />
            <Text style={{ color: c.onHero, fontSize: 11, fontWeight: '700', letterSpacing: 1.2 }}>THE BIG IDEA</Text>
          </View>
          <View style={{ borderWidth: 1, borderColor: c.heroMuted, borderRadius: 20, paddingHorizontal: 11, paddingVertical: 7 }}>
            <Text style={{ color: c.onHero, fontSize: 11, fontWeight: '700' }}>{post.insight.relevance_score} / 100 relevance</Text>
          </View>
        </View>
        <PostMedia post={post} onPress={open} />
        <Pressable accessibilityRole="button" accessibilityLabel={`Read ${post.insight.title}`} onPress={open} style={{ gap: 14, paddingVertical: 8 }}>
          <Text style={{ color: c.onHero, fontFamily: headline, fontSize: large ? 35 : 30, lineHeight: large ? 43 : 38, letterSpacing: -0.8 }}>{post.insight.title}</Text>
          <Text style={{ color: c.heroMuted, fontSize: large ? 18 : 14, lineHeight: large ? 28 : 23 }} numberOfLines={3}>{post.insight.summary}</Text>
        </Pressable>
        <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
          <MaterialButton mode="contained" onPress={open} accessibilityLabel={`Read ${post.insight.title}`}
            icon="arrow-top-right" buttonColor={c.onHero} textColor={c.hero}
            contentStyle={{ minHeight: 48 }}>Read the insight</MaterialButton>
          <IconButton icon={post.saved ? 'bookmark' : 'bookmark-outline'} iconColor={c.onHero}
            accessibilityLabel={post.saved ? 'Remove bookmark' : 'Save post'} accessibilityState={{ selected: post.saved }} onPress={save} size={23} />
        </View>
        <Text style={{ color: c.heroMuted, fontSize: 11 }}>{post.author || 'Author unavailable'} · {readingMinutes(post)} min read</Text>
      </Card.Content>
    </Card>
  </Animated.View>;
  return <Animated.View entering={reduced ? undefined : FadeInDown.duration(350).delay(Math.min(index, 5) * 50)}>
    <Card mode="elevated" elevation={1} style={{ backgroundColor: c.surface, borderRadius: 24 }}>
      <Card.Content style={{ padding: 20, gap: 16 }}>
        <PostMedia post={post} onPress={open} />
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
          <View style={{ width: 44, height: 44, borderRadius: 15, backgroundColor: c.accentBg, alignItems: 'center', justifyContent: 'center' }}>
            <TopicIcon name={post.insight.category} />
          </View>
          <View style={{ flex: 1, gap: 3 }}>
            <Label color={accent}>{post.insight.category}</Label>
            <Text style={{ color: c.muted, fontSize: 10 }}>{date} · {readingMinutes(post)} min read{post.read ? ' · Read' : ''}</Text>
          </View>
          <Text style={{ color: c.accentOnTint, backgroundColor: c.accentBg, borderRadius: 12, padding: 9, fontSize: 11, fontWeight: '700' }}>{post.insight.relevance_score}</Text>
        </View>
        <Pressable accessibilityRole="button" accessibilityLabel={`Read ${post.insight.title}`} onPress={open} style={{ gap: 10 }}>
          <Text style={{ color: c.text, fontWeight: '700', fontSize: large ? 25 : 21, lineHeight: large ? 33 : 28, letterSpacing: -0.4 }}>{post.insight.title}</Text>
          <Text style={{ color: c.ink, fontSize: large ? 17 : 14, lineHeight: large ? 27 : 23 }} numberOfLines={2}>{post.insight.summary}</Text>
        </Pressable>
        <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 7 }}>
          {post.insight.topics.slice(0, 2).map(topic => <Chip key={topic} compact mode="outlined"
            accessibilityLabel={`Explore ${topic}`} onPress={() => router.push({ pathname: '/discover', params: { topic } })}
            style={{ borderRadius: 10, backgroundColor: c.surface, minHeight: 44, justifyContent: 'center' }}
            textStyle={{ fontFamily: 'SignalRegular', fontSize: 11, color: c.muted }}>{topic}</Chip>)}
        </View>
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 9 }}>
          <Avatar.Text size={30} label={initials} color={c.accentOnTint}
            style={{ backgroundColor: c.accentBg }} labelStyle={{ fontFamily: 'SignalMedium', fontSize: 11 }} />
          <Text style={{ flex: 1, color: c.muted, fontSize: 12 }}>{post.author || 'Author unavailable'}</Text>
          <IconButton icon={post.saved ? 'bookmark' : 'bookmark-outline'} mode={post.saved ? 'contained-tonal' : undefined}
            iconColor={post.saved ? accent : c.muted} accessibilityState={{ selected: post.saved }}
            accessibilityLabel={post.saved ? 'Remove bookmark' : 'Save post'} onPress={save} size={20} />
        </View>
      </Card.Content>
    </Card>
  </Animated.View>;
}
