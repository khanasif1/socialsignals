import React, { useMemo } from 'react';
import { Platform } from 'react-native';
import { Stack } from 'expo-router';
import Head from 'expo-router/head';
import { StatusBar } from 'expo-status-bar';
import { useFonts } from 'expo-font';
import { Ionicons, MaterialCommunityIcons } from '@expo/vector-icons';
import { Inter_400Regular } from '@expo-google-fonts/inter/400Regular';
import { Inter_500Medium } from '@expo-google-fonts/inter/500Medium';
import { Inter_700Bold } from '@expo-google-fonts/inter/700Bold';
import { Manrope_800ExtraBold } from '@expo-google-fonts/manrope/800ExtraBold';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { PaperProvider } from 'react-native-paper';
import { useReducedMotion } from 'react-native-reanimated';
import { SignalProvider, useSignal } from '../hooks/useSignal';
import { usePalette } from '../components/Editorial';
import { materialTheme } from '../theme/material';

function Navigation() {
  const c = usePalette();
  const isDark = useSignal().preferences.theme === 'dark';
  const reducedMotion = useReducedMotion();
  const theme = useMemo(() => materialTheme(isDark, reducedMotion), [isDark, reducedMotion]);
  return <PaperProvider theme={theme}>
    {Platform.OS === 'web' && <Head><title>SIGNAL — Personal intelligence</title><meta name="description" content="Your private, distraction-free technical reader." /></Head>}
    <StatusBar style={isDark ? 'light' : 'dark'} />
    <Stack screenOptions={{ headerShown: false, contentStyle: { backgroundColor: c.bg }, animation: 'slide_from_right' }}>
      <Stack.Screen name="(tabs)" />
      <Stack.Screen name="post/[id]" />
    </Stack>
  </PaperProvider>;
}
export default function Layout() {
  const [loaded, error] = useFonts({
    ...Ionicons.font,
    ...MaterialCommunityIcons.font,
    SignalRegular: Inter_400Regular,
    SignalMedium: Inter_500Medium,
    SignalBold: Inter_700Bold,
    SignalDisplay: Manrope_800ExtraBold,
  });
  if (error) throw error;
  if (!loaded) return null;
  return <SafeAreaProvider><SignalProvider><Navigation /></SignalProvider></SafeAreaProvider>;
}
