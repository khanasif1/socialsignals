import React, { useState } from 'react';
import { View } from 'react-native';
import { TextInput } from 'react-native-paper';
import { Text } from '../../components/Typography';
import { Body, Button, Chips, Heading, Label, Page, Section, usePalette } from '../../components/Editorial';
import { useSignal } from '../../hooks/useSignal';
import type { Preferences } from '../../services/types';
import { bodyFont } from '../../theme';

export default function Settings() {
  const s = useSignal();
  const c = usePalette();
  const [secret, setSecret] = useState('');
  const [busy, setBusy] = useState(false);
  const [preferred, setPreferred] = useState('');
  const p = s.preferences;
  function update(patch: Partial<Preferences>) { void s.run(() => s.updatePreferences({ ...p, ...patch })); }
  async function login() {
    setBusy(true);
    try { await s.login(secret); setSecret(''); } finally { setBusy(false); }
  }
  const field = { backgroundColor: c.surface };
  return <Page>
    <Heading title="Make room for signal." subtitle="Private by design. Intentional by default." />
    <Section title="YOUR PRIVATE READER" />
    <Body muted>{s.demo ? 'You are exploring a fictional sample edition. Demo bookmarks and preferences stay on this device.' : s.token ? 'Signed in. Your session is stored securely on iOS.' : 'Sign in using the private passphrase configured on your backend.'}</Body>
    {(s.demo || !s.token) && <>
      <TextInput value={secret} onChangeText={setSecret} secureTextEntry autoCapitalize="none" autoCorrect={false}
        label="Private backend passphrase" mode="outlined" outlineStyle={{ borderRadius: 16 }}
        contentStyle={{ fontFamily: bodyFont }} accessibilityLabel="Private backend passphrase" style={field} />
      <Button label={busy ? 'Connecting…' : 'Connect private backend'} disabled={busy || !secret} icon="lock-closed-outline"
        onPress={() => void s.run(login)} />
    </>}
    <Button label={s.demo ? 'Leave demo mode' : 'Explore demo edition'} subtle onPress={() => void s.run(() => s.setDemo(!s.demo))} />
    {s.token && !s.demo && <Button label="Sign out" subtle onPress={() => void s.run(s.logout)} />}
    <Section title="LINKEDIN" detail={s.integration?.mode === 'crawler' ? 'Background collection' : s.integration?.connected ? 'Identity connected' : 'Export mode'} />
    <View style={{ backgroundColor: c.surface, borderRadius: 28, padding: 24, gap: 16 }}>
      <Label color={c.accent}>YOUR SOURCES. YOUR PRIVATE READER.</Label>
      <Body muted>Standard LinkedIn APIs do not expose your personal home feed. Import an authorized export, or configure the optional background browser worker on your server. Never enter your LinkedIn password in this app.</Body>
      {s.integration?.crawler?.enabled && <>
        <Text style={{ color: ['failed', 'action_required'].includes(s.integration.crawler.status) ? c.danger : c.muted, fontSize: 12, lineHeight: 19 }}>
          Background collection: {s.integration.crawler.status} · {s.integration.crawler.message}
        </Text>
        <Text style={{ color: c.muted, fontSize: 11, lineHeight: 18 }}>
          Last successful collection: {s.integration.crawler.last_success_at ? new Date(s.integration.crawler.last_success_at).toLocaleString() : 'Never'}
          {' · '}{s.integration.crawler.extracted} collected
          {s.integration.crawler.limit_reached ? ' · Run limit reached; feed coverage is incomplete' : ''}
        </Text>
        <Body muted>Account challenges require your action outside SIGNAL. Collection stays paused until the server worker is explicitly resumed. Automated access may violate LinkedIn terms and restrict your account.</Body>
      </>}
      <Button label="Connect / reconnect LinkedIn identity" disabled={s.demo || !s.token || !s.integration?.oauth_available}
        icon="link-outline" onPress={() => void s.run(s.connect)} />
      <Button label="Upload LinkedIn export" disabled={s.demo || !s.token} icon="cloud-upload-outline" subtle
        onPress={() => void s.run(s.importExport)} />
      <Text style={{ color: c.muted, fontSize: 11, lineHeight: 18 }}>Accepts Shares.csv, posts.json, or export ZIP (10 MiB). Only upload content you are authorized to process. Selected content is sent to your configured AI provider when synced.</Text>
      <Text style={{ color: c.muted, fontSize: 11, lineHeight: 18 }}>Source images use direct HTTPS links from an export or collected post. Your device loads them from the original host; links may expire. Text-only posts use labeled topic artwork. Image links are not sent to the AI provider.</Text>
      <Button label={s.syncStatus.status === 'running' ? 'Sync in progress…' : 'Sync imported posts'}
        disabled={s.demo || !s.token || s.syncStatus.status === 'running'} icon="sync-outline" onPress={() => void s.run(s.sync)} />
      <Text style={{ color: s.syncStatus.status === 'failed' ? c.danger : c.muted, fontSize: 12, lineHeight: 19 }}>{s.syncStatus.message}</Text>
      <Text style={{ color: c.muted, fontSize: 11 }}>Last sync: {s.syncStatus.finished_at ? new Date(s.syncStatus.finished_at).toLocaleString() : 'Never'} · {s.syncStatus.remaining} pending</Text>
    </View>
    <Section title="READING EXPERIENCE" />
    <Label>THEME</Label><Chips items={['dark', 'light']} selected={p.theme} onSelect={v => update({ theme: v as Preferences['theme'] })} />
    <Label>FONT SIZE</Label><Chips items={['standard', 'large']} selected={p.font_size} onSelect={v => update({ font_size: v as Preferences['font_size'] })} />
    <Label>PREFERRED TOPICS</Label>
    <Body muted>{p.preferred_topics.join(' · ') || 'Recommendations prioritize unread, technically relevant posts.'}</Body>
    <TextInput value={preferred} onChangeText={setPreferred} placeholder="Agentic AI, RAG, MCP"
      label="Preferred topics" mode="outlined" outlineStyle={{ borderRadius: 16 }} contentStyle={{ fontFamily: bodyFont }}
      accessibilityLabel="Preferred topics, comma separated" style={field} />
    <Button label="Update preferred topics" subtle onPress={() => update({ preferred_topics: preferred.split(',').map(t => t.trim()).filter(Boolean).slice(0, 20) })} />
    <Section title="CONTENT & SYNC" />
    <Label>RETENTION / BOOKMARKS ARE ALWAYS KEPT</Label>
    <Chips items={['1', '3', '7', '14', '30']} selected={String(p.retention_days)} onSelect={v => update({ retention_days: Number(v) as Preferences['retention_days'] })} />
    <Body muted>Days of imported raw and processed feed data to retain. Saved posts are stored independently.</Body>
    <Label>AUTOMATIC IMPORT PROCESSING</Label>
    <Chips items={['manual', 'hourly', 'daily']} selected={p.sync_frequency} onSelect={v => update({ sync_frequency: v as Preferences['sync_frequency'] })} />
    <Body muted>These preferences schedule processing of imported posts. The optional server WebJob has its own collection schedule and processes its batch even when this is set to manual.</Body>
    <Label>SUMMARY LENGTH</Label>
    <Chips items={['short', 'medium', 'long']} selected={p.summary_length} onSelect={v => update({ summary_length: v as Preferences['summary_length'] })} />
    <Label>MINIMUM RELEVANCE</Label>
    <Chips items={['0', '35', '60', '80']} selected={String(p.min_relevance_score)} onSelect={v => update({ min_relevance_score: Number(v) })} />
    <Label>MAXIMUM POSTS PER SYNC</Label>
    <Chips items={['25', '50', '100', '250', '500']} selected={String(p.max_posts_per_sync)} onSelect={v => update({ max_posts_per_sync: Number(v) })} />
    {s.statistics && <Body muted>{s.statistics.total_posts} posts extracted · {s.statistics.relevant_posts} retained · {s.statistics.unread_posts} unread</Body>}
    <View style={{ borderTopWidth: 1, borderColor: c.line, paddingTop: 24, gap: 12 }}>
      <Text style={{ color: c.text, letterSpacing: 4, fontWeight: '700' }}>SIGNAL / 1.0</Text>
      <Body muted>Your personal intelligence. No ads. No engagement metrics. No endless noise.</Body>
    </View>
  </Page>;
}
