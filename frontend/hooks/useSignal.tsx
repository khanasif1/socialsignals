import React, { createContext, useCallback, useContext, useEffect, useState } from 'react';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { AppState } from 'react-native';
import * as DocumentPicker from 'expo-document-picker';
import * as WebBrowser from 'expo-web-browser';
import samples from '../assets/posts.json';
import { api, credentials, upload } from '../services/api';
import type { Explanation, Integration, Post, Preferences, Statistics, SyncStatus } from '../services/types';

const defaults: Preferences = {
  retention_days: 3, max_posts_per_sync: 100, min_relevance_score: 35, summary_length: 'short',
  preferred_topics: [], sync_frequency: 'manual', theme: 'light', font_size: 'standard',
};
const emptySync: SyncStatus = {
  status: 'never', started_at: null, finished_at: null, imported: 0, relevant: 0,
  duplicates: 0, remaining: 0, message: 'Import an authorized LinkedIn export to begin.',
};
type State = {
  posts: Post[]; preferences: Preferences; demo: boolean; token: string | null;
  loading: boolean; error: string | null; notice: string | null;
  integration: Integration | null; syncStatus: SyncStatus; statistics: Statistics | null;
  refresh: () => Promise<void>; run: (action: () => Promise<unknown>) => Promise<void>;
  login: (secret: string) => Promise<void>; logout: () => Promise<void>;
  setDemo: (value: boolean) => Promise<void>; dismiss: () => void;
  save: (post: Post) => Promise<void>; markRead: (post: Post) => Promise<void>;
  updatePreferences: (preferences: Preferences) => Promise<void>;
  sync: () => Promise<void>; importExport: () => Promise<void>; connect: () => Promise<void>;
  explain: (post: Post) => Promise<Explanation>;
};
const Context = createContext<State | null>(null);

export function SignalProvider({ children }: { children: React.ReactNode }) {
  const [posts, setPosts] = useState<Post[]>([]);
  const [preferences, setPreferences] = useState(defaults);
  const [demo, setDemoState] = useState(process.env.EXPO_PUBLIC_DEMO !== 'false');
  const [token, setToken] = useState<string | null>(null);
  const [ready, setReady] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [integration, setIntegration] = useState<Integration | null>(null);
  const [statistics, setStatistics] = useState<Statistics | null>(null);
  const [syncStatus, setSyncStatus] = useState(emptySync);

  const run = useCallback(async (action: () => Promise<unknown>) => {
    setError(null);
    try { await action(); } catch (e) { setError(e instanceof Error ? e.message : 'Something went wrong. Please retry.'); }
  }, []);

  useEffect(() => {
    void run(async () => {
      try {
        const [session, mode, cached] = await Promise.all([
          credentials.get(), AsyncStorage.getItem('signal-mode'), AsyncStorage.getItem('signal-demo'),
        ]);
        setToken(session);
        const isDemo = mode ? mode === 'demo' : process.env.EXPO_PUBLIC_DEMO !== 'false';
        setDemoState(isDemo);
        if (isDemo && cached) {
          const data = JSON.parse(cached) as { posts: Post[]; preferences: Preferences };
          setPosts(data.posts); setPreferences(data.preferences);
        } else setPosts(isDemo ? samples as Post[] : []);
      } finally { setReady(true); }
    });
  }, [run]);

  const refresh = useCallback(async () => {
    if (demo || !token) return;
    setLoading(true);
    try {
      const [first, saved, prefs, status, connection, stats] = await Promise.all([
        api<{ items: Post[]; total: number }>('/posts?page_size=100', token),
        api<Post[]>('/bookmarks', token), api<Preferences>('/settings', token),
        api<SyncStatus>('/linkedin/sync/status', token), api<Integration>('/linkedin/status', token),
        api<Statistics>('/statistics', token),
      ]);
      const all = [...first.items];
      for (let page = 2; all.length < first.total; page++) {
        const next = await api<{ items: Post[] }>(`/posts?page_size=100&page=${page}`, token);
        if (!next.items.length) break;
        all.push(...next.items);
      }
      const merged = new Map(all.map(p => [p.id, p]));
      saved.forEach(p => merged.set(p.id, p));
      setPosts([...merged.values()]); setPreferences(prefs); setSyncStatus(status);
      setIntegration(connection); setStatistics(stats);
    } finally { setLoading(false); }
  }, [demo, token]);

  useEffect(() => { if (ready) void run(refresh); }, [ready, refresh, run]);
  useEffect(() => {
    if (!ready || demo || !token) return;
    const timer = setInterval(() => {
      if (AppState.currentState === 'active') void run(refresh);
    }, 60_000);
    const subscription = AppState.addEventListener('change', state => {
      if (state === 'active') void run(refresh);
    });
    return () => { clearInterval(timer); subscription.remove(); };
  }, [ready, demo, token, refresh, run]);
  useEffect(() => {
    if ((syncStatus.status !== 'running' && integration?.crawler?.status !== 'running') || demo || !token) return;
    const timer = setInterval(() => { void run(refresh); }, 4000);
    return () => clearInterval(timer);
  }, [syncStatus.status, integration?.crawler?.status, demo, token, refresh, run]);
  useEffect(() => {
    if (ready && demo) void run(() => AsyncStorage.setItem('signal-demo', JSON.stringify({ posts, preferences })));
  }, [posts, preferences, demo, ready, run]);

  async function setDemo(value: boolean) {
    await AsyncStorage.setItem('signal-mode', value ? 'demo' : 'live');
    setPosts(value ? samples as Post[] : []);
    setPreferences(defaults); setStatistics(null); setIntegration(null); setSyncStatus(emptySync);
    setError(null); setNotice(null); setDemoState(value);
    if (value) {
      const cached = await AsyncStorage.getItem('signal-demo');
      if (cached) {
        const data = JSON.parse(cached) as { posts: Post[]; preferences: Preferences };
        setPosts(data.posts); setPreferences(data.preferences);
      }
    }
  }
  async function login(secret: string) {
    const result = await api<{ token: string }>('/auth/login', null, 'POST', { secret });
    await credentials.set(result.token);
    await AsyncStorage.setItem('signal-mode', 'live');
    setPosts([]); setDemoState(false); setToken(result.token); setNotice('Your private reader is connected.');
  }
  async function logout() {
    if (token) await api('/auth/session', token, 'DELETE');
    await credentials.clear(); setToken(null); setPosts([]); setStatistics(null); setIntegration(null);
  }
  async function save(post: Post) {
    if (!demo) await api(`/bookmarks/${post.id}`, token, post.saved ? 'DELETE' : 'POST');
    setPosts(current => current.map(p => p.id === post.id ? { ...p, saved: !post.saved } : p));
  }
  async function markRead(post: Post) {
    if (!demo) await api(`/posts/${post.id}/read`, token, 'PUT', { read: !post.read });
    setPosts(current => current.map(p => p.id === post.id ? { ...p, read: !post.read } : p));
  }
  async function updatePreferences(value: Preferences) {
    if (!demo) await api('/settings', token, 'PUT', value);
    setPreferences(value);
  }
  async function sync() {
    if (demo) { setNotice('Demo mode uses synthetic posts. Connect your backend in Settings to import real exports.'); return; }
    const result = await api<SyncStatus>('/linkedin/sync', token, 'POST');
    setSyncStatus(result);
  }
  async function importExport() {
    if (demo || !token) throw new Error('Connect your private backend before uploading an export.');
    const result = await DocumentPicker.getDocumentAsync({
      type: ['text/csv', 'application/json', 'application/zip', 'application/x-zip-compressed', 'text/comma-separated-values'],
      copyToCacheDirectory: true,
    });
    if (result.canceled || !result.assets[0]) return;
    if ((result.assets[0].size || 0) > 10 * 1024 * 1024) throw new Error('Export must be at most 10 MiB.');
    const response = await upload(result.assets[0], token);
    setNotice(response.message);
  }
  async function connect() {
    const result = await api<{ authorization_url: string }>('/linkedin/connect', token, 'POST');
    await WebBrowser.openBrowserAsync(result.authorization_url);
    await refresh();
  }
  async function explain(post: Post): Promise<Explanation> {
    if (!demo) return api<Explanation>(`/posts/${post.id}/explain`, token, 'POST');
    return {
      executive: `Demo interpretation: ${post.insight.main_insight}`,
      architect: `Demo interpretation: ${post.insight.patterns.join(' and ')}. ${post.insight.practical_relevance}`,
      technical: `Demo interpretation, not a live AI response: ${post.insight.why_it_matters}\n\nThe synthetic source does not supply code, measured results, or a full implementation. Those details cannot be inferred.`,
      generated: true,
    };
  }

  return <Context.Provider value={{
    posts: demo || token ? posts : [], preferences, demo, token, loading: loading || !ready, error, notice,
    integration, syncStatus, statistics, refresh, run, login, logout, setDemo,
    dismiss: () => { setError(null); setNotice(null); }, save, markRead, updatePreferences,
    sync, importExport, connect, explain,
  }}>{children}</Context.Provider>;
}
export function useSignal() {
  const value = useContext(Context);
  if (!value) throw new Error('SignalProvider missing');
  return value;
}
