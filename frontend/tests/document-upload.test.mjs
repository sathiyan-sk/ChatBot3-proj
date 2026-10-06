import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import axios from 'axios';

const pagePath = new URL('../src/pages/ApplicationDetail.jsx', import.meta.url);

test('document uploads override the shared JSON content type', async () => {
  const source = await readFile(pagePath, 'utf8');

  assert.match(
    source,
    /apiClient\.post\("\/admin\/documents\/upload",\s*form,\s*\{\s*headers:\s*\{\s*"Content-Type":\s*"multipart\/form-data"/s,
  );

  const form = new FormData();
  form.append('knowledge_base_id', '946ad52a-5013-42e0-9430-36f82697d681');
  form.append('title', 'guide.txt');
  form.append('file', new Blob(['test content']), 'guide.txt');
  const headers = new axios.AxiosHeaders({
    'Content-Type': 'multipart/form-data',
  });
  const transformed = axios.defaults.transformRequest[0](form, headers);

  assert.equal(transformed, form);

  const jsonHeaders = new axios.AxiosHeaders({
    'Content-Type': 'application/json',
  });
  const incorrectlyTransformed = axios.defaults.transformRequest[0](
    form,
    jsonHeaders,
  );
  assert.equal(typeof incorrectlyTransformed, 'string');
});
