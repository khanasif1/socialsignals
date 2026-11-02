export default {
  expo: {
    name: 'SIGNAL',
    slug: 'signal-reader',
    scheme: 'signal',
    version: '1.0.0',
    icon: './assets/icon.png',
    splash: { backgroundColor: '#212623', image: './assets/icon.png', resizeMode: 'contain' },
    orientation: 'portrait',
    userInterfaceStyle: 'automatic',
    ios: {
      supportsTablet: false,
      bundleIdentifier: process.env.EXPO_PUBLIC_IOS_BUNDLE_ID || 'com.yourcompany.signal',
      infoPlist: { ITSAppUsesNonExemptEncryption: false },
    },
    plugins: ['expo-router', 'expo-secure-store', 'expo-document-picker'],
    web: { bundler: 'metro', output: 'static', name: 'SIGNAL' },
    experiments: { typedRoutes: true },
    extra: { eas: { projectId: process.env.EXPO_PUBLIC_EAS_PROJECT_ID || undefined } },
  },
};
