import React from 'react';
import { Tabs } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { useWindowDimensions, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { bodyFont } from '../../theme';
import { usePalette } from '../../components/Editorial';

const icons = {
  index: 'sunny-outline', discover: 'compass-outline', topics: 'grid-outline',
  saved: 'bookmark-outline', settings: 'options-outline',
} as const;
export default function TabLayout() {
  const c = usePalette();
  const wide = useWindowDimensions().width >= 900;
  const insets = useSafeAreaInsets();
  return <Tabs screenOptions={{
    headerShown: false, tabBarActiveTintColor: c.accent, tabBarInactiveTintColor: c.muted,
    tabBarStyle: { display: wide ? 'none' : 'flex', backgroundColor: c.surface, borderTopWidth: 0, paddingTop: 10, height: 70 + insets.bottom },
    tabBarLabelStyle: { fontFamily: bodyFont, fontSize: 10, paddingBottom: 6 },
    sceneStyle: { backgroundColor: c.bg },
  }}>
    {Object.entries(icons).map(([name, icon]) => <Tabs.Screen key={name} name={name} options={{
      title: name === 'index' ? 'Today' : name[0]!.toUpperCase() + name.slice(1),
      tabBarIcon: ({ color, focused }) => <View style={{ borderRadius: 20, width: 56, height: 30,
        backgroundColor: focused ? c.accentBg : 'transparent', alignItems: 'center', justifyContent: 'center' }}>
        <Ionicons name={icon} color={color} size={21} />
      </View>,
    }} />)}
  </Tabs>;
}
