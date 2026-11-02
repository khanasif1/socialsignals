import { strict as assert } from 'node:assert';
import { test } from 'node:test';
import { dark, light } from '../../frontend/theme/colors';

function luminance(hex: string) {
  const rgb = [1, 3, 5].map(i => {
    const channel = parseInt(hex.slice(i, i + 2), 16) / 255;
    return channel <= 0.04045 ? channel / 12.92 : ((channel + 0.055) / 1.055) ** 2.4;
  });
  return rgb[0]! * 0.2126 + rgb[1]! * 0.7152 + rgb[2]! * 0.0722;
}
function contrast(foreground: string, background: string) {
  const a = luminance(foreground), b = luminance(background);
  return (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
}

test('editorial reading text and controls retain accessible contrast in both themes', () => {
  for (const palette of [dark, light]) {
    for (const background of [palette.bg, palette.surface, palette.raised, palette.accentBg]) {
      assert.ok(contrast(palette.text, background) >= 4.5, `${background}: body text`);
      assert.ok(contrast(palette.ink, background) >= 4.5, `${background}: long-form text`);
      assert.ok(contrast(palette.muted, background) >= 4.5, `${background}: secondary text`);
      assert.ok(contrast(palette.accentOnTint, background) >= 4.5, `${background}: tinted-surface label`);
    }
    assert.ok(contrast(palette.accent, palette.surface) >= 4.5);
    assert.ok(contrast(palette.accent, palette.raised) >= 3, 'large briefing numbers');
    assert.ok(contrast(palette.buttonText, palette.button) >= 4.5);
    assert.ok(contrast(palette.bg, palette.accent) >= 4.5);
  }
});
test('Material app bars and coloured containers retain readable foregrounds', () => {
  for (const palette of [dark, light]) {
    assert.ok(contrast(palette.onMasthead, palette.masthead) >= 4.5);
    assert.ok(contrast(palette.onMastheadMuted, palette.masthead) >= 4.5);
    assert.ok(contrast(palette.onHero, palette.hero) >= 4.5);
    assert.ok(contrast(palette.heroMuted, palette.hero) >= 4.5);
    assert.ok(contrast(palette.onSecondaryContainer, palette.secondaryContainer) >= 4.5);
    assert.ok(contrast(palette.onTertiaryContainer, palette.tertiaryContainer) >= 4.5);
  }
});
test('Material editions retain red titles with distinct layered surfaces', () => {
  assert.equal(light.bg, '#FFF8F7');
  assert.equal(light.surface, '#FFFFFF');
  assert.equal(light.masthead, light.surface);
  assert.equal(light.text, '#D71920');
  assert.equal(light.accent, light.text);
  assert.equal(dark.text, '#FF7373');
  assert.equal(dark.accent, dark.text);
  assert.equal(light.highlight, '#F23D45');
  assert.notEqual(light.raised, light.surface);
  assert.notEqual(dark.raised, dark.surface);
  assert.equal(light.button, light.accent);
});
