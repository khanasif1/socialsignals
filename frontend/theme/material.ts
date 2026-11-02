import { configureFonts, MD3DarkTheme, MD3LightTheme, type MD3Theme } from 'react-native-paper';
import { bodyFont, headline } from './index';
import { dark, light } from './colors';

export function materialTheme(isDark: boolean, reducedMotion: boolean): MD3Theme {
  const base = isDark ? MD3DarkTheme : MD3LightTheme;
  const c = isDark ? dark : light;
  const fonts = configureFonts({ config: { fontFamily: bodyFont } });
  return {
    ...base,
    roundness: 6,
    animation: { scale: reducedMotion ? 0 : 1 },
    fonts: {
      ...fonts,
      headlineLarge: { ...fonts.headlineLarge, fontFamily: headline, fontWeight: 'normal' },
      titleLarge: { ...fonts.titleLarge, fontFamily: 'SignalBold', fontWeight: 'normal' },
      labelLarge: { ...fonts.labelLarge, fontFamily: 'SignalBold', fontWeight: 'normal' },
    },
    colors: {
      ...base.colors,
      primary: c.button, onPrimary: c.buttonText,
      primaryContainer: c.accentBg, onPrimaryContainer: c.accentOnTint,
      secondaryContainer: c.secondaryContainer, onSecondaryContainer: c.onSecondaryContainer,
      tertiaryContainer: c.tertiaryContainer, onTertiaryContainer: c.onTertiaryContainer,
      background: c.bg, onBackground: c.ink,
      surface: c.surface, onSurface: c.ink,
      surfaceVariant: c.raised, onSurfaceVariant: c.muted,
      outline: c.line, outlineVariant: c.line, error: c.danger,
      elevation: {
        level0: 'transparent', level1: c.surface, level2: c.raised,
        level3: c.raised, level4: c.raised, level5: c.raised,
      },
    },
  };
}
