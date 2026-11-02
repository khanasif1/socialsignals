import { strict as assert } from 'node:assert';
import { test } from 'node:test';
import { isSourceImageUrl } from '../../frontend/services/media';

test('source images accept HTTPS links including CDN query strings', () => {
  assert.ok(isSourceImageUrl('https://media.licdn.com/dms/image/example.jpg'));
  assert.ok(isSourceImageUrl('https://cdn.example.com/image.png?view=original&size=large'));
});

test('source images reject unsafe schemes, relative paths and embedded credentials', () => {
  for (const url of ['', '/image.jpg', 'not a URL', 'http://example.com/image.jpg',
    'javascript:alert(1)', 'data:image/png;base64,abc', 'file:///image.png',
    'https://member:password@example.com/image.jpg']) {
    assert.equal(isSourceImageUrl(url), false, url);
  }
});
