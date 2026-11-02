import React, { useState } from 'react';
import { Image, Platform, Pressable, View } from 'react-native';
import { MaterialCommunityIcons } from '@expo/vector-icons';
import { ActivityIndicator, Button } from 'react-native-paper';
import { useSignal } from '../hooks/useSignal';
import { dark, light } from '../theme';
import { isSourceImageUrl } from '../services/media';
import type { Post } from '../services/types';
import { Text } from './Typography';

function useMediaPalette() {
  return useSignal().preferences.theme === 'light' ? light : dark;
}

function TopicArtwork({ post }: { post: Post }) {
  const c = useMediaPalette();
  const topic = post.insight.topics[0] || post.insight.category;
  const variant = /rag|retrieval/i.test(topic) ? 'retrieval'
    : /security|trust|mcp/i.test(topic) ? 'security' : /agent/i.test(topic) ? 'agents' : 'context';
  const background = variant === 'retrieval' ? c.secondaryContainer : variant === 'security' ? c.tertiaryContainer : c.accentBg;
  const ink = variant === 'retrieval' ? c.onSecondaryContainer : variant === 'security' ? c.onTertiaryContainer : c.accentOnTint;
  const icon = variant === 'retrieval' ? 'database-search-outline'
    : variant === 'security' ? 'shield-check-outline' : variant === 'agents' ? 'robot-outline' : 'layers-triple-outline';
  return <View accessibilityElementsHidden importantForAccessibility="no-hide-descendants"
    style={{ flex: 1, backgroundColor: background, overflow: 'hidden', justifyContent: 'center', alignItems: 'center' }}>
    <View style={{ position: 'absolute', width: 270, height: 270, borderWidth: 1, borderRadius: 135, borderColor: ink, opacity: 0.14 }} />
    <View style={{ position: 'absolute', width: 200, height: 200, borderWidth: 1, borderRadius: 100, borderColor: ink, opacity: 0.2 }} />
    <View style={{ position: 'absolute', width: '75%', height: 1, backgroundColor: ink, opacity: 0.25, transform: [{ rotate: '-12deg' }] }} />
    <View style={{ position: 'absolute', left: '12%', top: '25%', width: 48, height: 56, borderRadius: 12, padding: 10,
      backgroundColor: c.surface, gap: 6, transform: [{ rotate: '-12deg' }] }}>
      {[90, 65, 80].map((width, index) => <View key={index} style={{ width: `${width}%`, height: 5, borderRadius: 3, backgroundColor: ink, opacity: 0.3 + index * 0.2 }} />)}
    </View>
    <View style={{ width: 90, height: 90, borderRadius: 28, backgroundColor: c.surface, alignItems: 'center',
      justifyContent: 'center', borderWidth: 1, borderColor: background, transform: [{ rotate: variant === 'agents' ? '-8deg' : '8deg' }] }}>
      <MaterialCommunityIcons name={icon} color={ink} size={46} />
    </View>
    <View style={{ position: 'absolute', right: '12%', bottom: '25%', width: 44, height: 44, borderRadius: 22,
      backgroundColor: ink, alignItems: 'center', justifyContent: 'center' }}>
      <MaterialCommunityIcons name={variant === 'security' ? 'check' : 'arrow-top-right'} color={background} size={23} />
    </View>
    <Text style={{ position: 'absolute', top: 16, left: 18, right: 18, color: ink, fontSize: 10,
      fontWeight: '700', letterSpacing: 1.2 }} numberOfLines={1}>{topic.toUpperCase()}</Text>
  </View>;
}

function SourceImage({ url, post, index, count, expanded, onPress }: {
  url: string; post: Post; index: number; count: number; expanded: boolean; onPress?: () => void;
}) {
  const c = useMediaPalette();
  const [failed, setFailed] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const [ratio, setRatio] = useState(16 / 9);
  const [attempt, setAttempt] = useState(0);
  const allowed = isSourceImageUrl(url);
  const unavailable = !allowed || failed;
  const label = `Source image ${index + 1} of ${count} for ${post.insight.title}`;
  const imageLoaded = (width: number, height: number) => {
    if (width > 0 && height > 0) setRatio(width / height);
    setLoaded(true);
  };
  const retry = () => { setFailed(false); setLoaded(false); setAttempt(value => value + 1); };
  const frame = <View style={{ width: '100%', aspectRatio: expanded ? ratio : 16 / 9,
    maxHeight: expanded ? 720 : 240, overflow: 'hidden', backgroundColor: c.raised }}>
    {unavailable ? <TopicArtwork post={post} /> : <>
      {Platform.OS === 'web' ? <img key={attempt} src={url} alt={label} loading="lazy" decoding="async" referrerPolicy="no-referrer"
        style={{ display: 'block', width: '100%', height: '100%', objectFit: expanded ? 'contain' : 'cover' }}
        onLoad={event => imageLoaded(event.currentTarget.naturalWidth, event.currentTarget.naturalHeight)}
        onError={() => setFailed(true)} />
        : <Image key={attempt} source={{ uri: url }} accessibilityLabel={label}
          resizeMode={expanded ? 'contain' : 'cover'} style={{ width: '100%', height: '100%' }}
          onLoad={event => imageLoaded(event.nativeEvent.source.width, event.nativeEvent.source.height)}
          onError={() => setFailed(true)} />}
      {!loaded && <View pointerEvents="none" style={{ position: 'absolute', top: 0, right: 0, bottom: 0, left: 0,
        alignItems: 'center', justifyContent: 'center' }}>
        <ActivityIndicator accessibilityLabel="Loading source image" color={c.accent} />
      </View>}
    </>}
  </View>;
  return <View style={{ borderRadius: 18, overflow: 'hidden', backgroundColor: c.surface }}>
    {onPress ? <Pressable onPress={onPress} accessibilityRole="button" accessibilityLabel={`Read ${post.insight.title}`}>{frame}</Pressable> : frame}
    <View style={{ paddingHorizontal: 14, paddingVertical: 9, flexDirection: 'row', flexWrap: 'wrap', gap: 6, alignItems: 'center' }}>
      <Text accessibilityLiveRegion={unavailable ? 'polite' : 'none'} style={{ color: c.muted, fontSize: 11, lineHeight: 17, flex: 1 }}>
        {unavailable ? (allowed ? 'Source image unavailable. The link may have expired.' : 'Unsupported source image link.')
          : `Source image${count > 1 ? ` ${index + 1} of ${count}${expanded ? '' : ' · Open post to view all'}` : ''}`}
      </Text>
      {failed && allowed && <Button mode="text" onPress={retry} accessibilityLabel="Retry source image"
        contentStyle={{ minHeight: 44 }} textColor={c.accent}>Retry</Button>}
    </View>
  </View>;
}

export function PostMedia({ post, expanded = false, onPress }: { post: Post; expanded?: boolean; onPress?: () => void }) {
  const c = useMediaPalette();
  const urls = [...new Set(post.image_urls || [])].slice(0, 10);
  if (!urls.length) {
    const artwork = <View style={{ width: '100%', aspectRatio: 16 / 9, maxHeight: 240, overflow: 'hidden' }}><TopicArtwork post={post} /></View>;
    return <View style={{ borderRadius: 18, overflow: 'hidden', backgroundColor: c.surface }}>
      {onPress ? <Pressable onPress={onPress} accessibilityRole="button" accessibilityLabel={`Read ${post.insight.title}`}>{artwork}</Pressable> : artwork}
      <Text style={{ color: c.muted, paddingHorizontal: 14, paddingVertical: 9, fontSize: 11, lineHeight: 17 }}>
        Original topic artwork · No source image supplied
      </Text>
    </View>;
  }
  return <View style={{ gap: 16 }}>
    {(expanded ? urls : urls.slice(0, 1)).map((url, index) =>
      <SourceImage key={url} url={url} post={post} index={index} count={urls.length} expanded={expanded} onPress={onPress} />)}
  </View>;
}
