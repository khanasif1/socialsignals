import { Platform } from 'react-native';
import * as SecureStore from 'expo-secure-store';
import type { DocumentPickerAsset } from 'expo-document-picker';
import { File } from 'expo-file-system';

const base = (process.env.EXPO_PUBLIC_API_URL || 'http://localhost:8000').replace(/\/$/, '');
const key = 'signal-session';

export const credentials = {
  async get() {
    return Platform.OS === 'web' ? sessionStorage.getItem(key) : SecureStore.getItemAsync(key);
  },
  async set(token: string) {
    if (Platform.OS === 'web') sessionStorage.setItem(key, token);
    else await SecureStore.setItemAsync(key, token, { keychainAccessible: SecureStore.WHEN_UNLOCKED_THIS_DEVICE_ONLY });
  },
  async clear() {
    if (Platform.OS === 'web') sessionStorage.removeItem(key);
    else await SecureStore.deleteItemAsync(key);
  },
};

export async function api<T>(path: string, token: string | null, method = 'GET', body?: unknown): Promise<T> {
  if (!base.startsWith('https://') && !__DEV__) throw new Error('Production API must use HTTPS.');
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), path.endsWith('/explain') ? 180000 : 60000);
  try {
    const response = await fetch(`${base}/api${path}`, {
      method,
      headers: {
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...(body !== undefined ? { 'Content-Type': 'application/json' } : {}),
      },
      body: body !== undefined ? JSON.stringify(body) : undefined,
      signal: controller.signal,
    });
    if (!response.ok) {
      const error = await response.json().catch(() => null);
      if (response.status === 401) throw new Error('Session expired or invalid passphrase. Sign in from Settings.');
      throw new Error(typeof error?.detail === 'string' ? error.detail : `Request failed (${response.status}).`);
    }
    return await response.json() as T;
  } finally {
    clearTimeout(timeout);
  }
}

export async function upload(asset: DocumentPickerAsset, token: string) {
  if (!base.startsWith('https://') && !__DEV__) throw new Error('Production API must use HTTPS.');
  const form = new FormData();
  const file = Platform.OS === 'web' ? asset.file : new File(asset.uri);
  if (!file) throw new Error('Could not read the selected export.');
  form.append('file', file, asset.name);
  // Expo's fetch supports native file-system File bodies without base64 expansion.
  const { fetch: expoFetch } = await import('expo/fetch');
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 120000);
  try {
    const response = await expoFetch(`${base}/api/linkedin/import`, {
      method: 'POST', headers: { Authorization: `Bearer ${token}` }, body: form, signal: controller.signal,
    });
    if (!response.ok) {
      const error = await response.json();
      throw new Error(typeof error?.detail === 'string' ? error.detail : 'Export upload failed.');
    }
    return await response.json() as { message: string };
  } finally {
    clearTimeout(timeout);
  }
}
