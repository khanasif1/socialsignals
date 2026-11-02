import React from 'react';
import { StyleSheet, Text as NativeText, type TextProps } from 'react-native';
import { bodyFont, headline } from '../theme';

export const Text = React.forwardRef<NativeText, TextProps>(function Text({ style, ...props }, ref) {
  const flattened = StyleSheet.flatten(style);
  const weight = Number(flattened?.fontWeight || 400);
  const fontFamily = flattened?.fontFamily === headline ? headline
    : weight >= 600 ? 'SignalBold' : weight >= 500 ? 'SignalMedium' : bodyFont;
  return <NativeText ref={ref} {...props} style={[style, { fontFamily, fontWeight: 'normal' }]} />;
});
