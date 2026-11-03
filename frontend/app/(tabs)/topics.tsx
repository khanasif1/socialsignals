import React from 'react';
import { Pressable, useWindowDimensions, View } from 'react-native';
import { Card } from 'react-native-paper';
import { MaterialCommunityIcons } from '@expo/vector-icons';
import { Text } from '../../components/Typography';
import { router } from 'expo-router';
import { Empty, Heading, Label, Page, TopicIcon, usePalette } from '../../components/Editorial';
import { useSignal } from '../../hooks/useSignal';
import { topicGroups } from '../../services/reading';
import { headline } from '../../theme';
export default function Topics() {
  const s = useSignal();
  const c = usePalette();
  const wide = useWindowDimensions().width >= 900;
  const groups = topicGroups(s.posts);
  return <Page>
    <Heading title="Follow your curiosity." subtitle="A constellation of ideas. Pick a topic and connect the dots." />
    <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 20 }}>
    {groups.map(({ name, posts }, index) => {
      return <Pressable key={name} accessibilityRole="button" accessibilityLabel={`Explore ${name}`}
        onPress={() => router.push({ pathname: '/discover', params: { topic: name } })}
        style={{ width: wide ? '47%' : '100%', flexGrow: 1 }}>
        <Card mode="elevated" elevation={1}
          style={{ backgroundColor: c.surface, borderRadius: 28, flexGrow: 1 }}>
        <Card.Content style={{ padding: 24, gap: 18 }}>
          <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' }}>
            <View style={{ padding: 14, borderRadius: 19, backgroundColor: index % 2 ? c.raised : c.accentBg }}>
              <TopicIcon name={name} size={28} />
            </View>
            <MaterialCommunityIcons name="arrow-top-right" color={c.accent} size={23} />
          </View>
          <Text style={{ fontFamily: headline, fontSize: 27, color: c.text }}>{name}</Text>
          <Text style={{ color: c.muted, fontSize: 12 }}>{posts.length} insights · Latest: {posts.reduce<string | null>((latest, p) =>
            p.published_at && (!latest || p.published_at > latest) ? p.published_at : latest, null)?.slice(0, 10) || 'Date unavailable'}</Text>
          <View style={{ backgroundColor: c.raised, borderRadius: 18, padding: 16, gap: 8 }}>
            <Label color={c.accentOnTint}>Start here</Label><Text style={{ color: c.ink, fontSize: 14, lineHeight: 22 }}>{posts[0]?.insight.title}</Text>
          </View>
        </Card.Content>
        </Card>
      </Pressable>;
    })}
    </View>
    {!groups.length && <Empty />}
  </Page>;
}
