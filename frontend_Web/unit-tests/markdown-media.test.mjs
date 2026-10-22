import test from 'node:test';
import assert from 'node:assert/strict';
import { resolveSourceUrl, previewAssetMarkdown } from '../src/services/markdownMedia.js';
const source = 'https://github.com/owner/repo';
const metadata = {commit:'abc123', readme_path:'docs/README.md'};
test('GitHub images and links use the pinned version and README directory', () => {
  assert.equal(resolveSourceUrl('../images/figure 1.png',source,metadata,true),'https://raw.githubusercontent.com/owner/repo/abc123/images/figure%201.png');
  assert.equal(resolveSourceUrl('./guide.md',source,metadata),'https://github.com/owner/repo/blob/abc123/docs/guide.md');
  assert.equal(resolveSourceUrl('/images/logo.png',source,metadata,true),'https://raw.githubusercontent.com/owner/repo/abc123/images/logo.png');
  assert.equal(resolveSourceUrl('./pics/a.png',source,{},true),'https://raw.githubusercontent.com/owner/repo/HEAD/pics/a.png');
});
test('absolute URLs, anchors and workbench attachment references stay intact', () => {
  for(const url of ['https://example.org/a.png','#section','/api/attachments/id/content','//example.org/a.png']) {
    assert.equal(resolveSourceUrl(url,source,metadata,true),url);
  }
  assert.equal(resolveSourceUrl('https://github.com/a/b/blob/main/a.png',source,{},true),'https://raw.githubusercontent.com/a/b/main/a.png');
  assert.equal(resolveSourceUrl('./a.png','https://example.org/page',{},true),'./a.png');
});
test('staged image links are substituted only for rendering, without mutating note text', () => {
  const id='11111111-1111-4111-8111-111111111111';
  const original=`![original](import-asset://${id})`;
  assert.equal(previewAssetMarkdown(original,[{id,preview_url:'/api/source-imports/assets/token/image'}]),'![original](/api/source-imports/assets/token/image)');
  assert.equal(original,`![original](import-asset://${id})`);
});
