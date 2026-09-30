import { readFile } from 'node:fs/promises';
import test from 'node:test';
import assert from 'node:assert/strict';

const filePath = new URL('../public/widget/widget.js', import.meta.url);

test('disabled widget config must stop rendering immediately', async () => {
  const source = await readFile(filePath, 'utf8');

  assert.match(
    source,
    /}\s*else\s*\{\s*console\.warn\([\s\S]*?Failed to load configuration[\s\S]*?\);\s*return;\s*\}/m,
    'Widget should exit before rendering when backend rejects config fetch.'
  );
});
