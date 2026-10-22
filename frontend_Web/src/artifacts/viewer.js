// This renderer is also embedded verbatim in offline HTML. Keep it dependency-free.
// User content only reaches textContent, never HTML, event handlers, or scripts.
export function mountPathArtifact(root, artifact, catalogs, initialLanguage = 'zh', options = {}) {
  let language = initialLanguage === 'en' ? 'en' : 'zh';
  let selected = artifact.objects[0]?.id || null;
  const objects = new Map(artifact.objects.map(object => [object.id, object]));
  const tr = (key, values = {}) => (catalogs[language][key] || key).replace(/\{(\w+)\}/g,
    (match, name) => Object.hasOwn(values, name) ? String(values[name]) : match);
  const node = (tag, className, text) => {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (text != null) element.textContent = text;
    return element;
  };
  const svg = (tag, attributes = {}, text) => {
    const element = document.createElementNS('http://www.w3.org/2000/svg', tag);
    for (const [key, value] of Object.entries(attributes)) element.setAttribute(key, value);
    if (text != null) element.textContent = text;
    return element;
  };
  function copy(container, text) {
    // A deliberately small, inert Markdown presentation. Original text is retained.
    let code = false;
    let block;
    for (const line of (text || '').split('\n')) {
      if (line.startsWith('```')) {
        code = !code;
        if (code) { block = node('pre', 'artifact-code'); container.append(block); }
      } else if (code) block.textContent += line + '\n';
      else if (/^#{1,6}\s/.test(line)) container.append(node('h3', '', line.replace(/^#{1,6}\s+/, '')));
      else if (line.trim()) container.append(node('p', 'artifact-copy', line));
    }
  }
  function source(container, url, label) {
    if (!url) return;
    try {
      const parsed = new URL(url);
      if (!['http:', 'https:'].includes(parsed.protocol) || parsed.username || parsed.password) return;
      const link = node('a', 'artifact-source', label || url);
      link.href = parsed.href;
      link.target = '_blank';
      link.rel = 'noopener noreferrer';
      container.append(link);
    } catch { /* Invalid imported sources are never made clickable. */ }
  }
  function graph(container) {
    if (!artifact.objects.length) {
      container.append(node('p', 'artifact-muted', tr('artifact.noNodes')));
      return;
    }
    const columns = Math.min(3, artifact.objects.length);
    const width = columns * 280;
    const height = Math.ceil(artifact.objects.length / columns) * 150 + 40;
    const positions = new Map(artifact.objects.map((object, index) => [object.id,
      { x: index % columns * 280 + 140, y: Math.floor(index / columns) * 150 + 70 }]));
    const canvas = svg('svg', { viewBox: `0 0 ${width} ${height}`, role: 'img',
      'aria-label': tr('artifact.graph'), class: 'artifact-graph', width, height });
    const defs = svg('defs');
    const marker = svg('marker', { id: 'artifact-arrow', viewBox: '0 0 10 10', refX: 9,
      refY: 5, markerWidth: 6, markerHeight: 6, orient: 'auto-start-reverse' });
    marker.append(svg('path', { d: 'M 0 0 L 10 5 L 0 10 z', fill: '#91a79c' }));
    defs.append(marker);
    canvas.append(defs);
    for (const relation of artifact.relations) {
      const a = positions.get(relation.source_id), b = positions.get(relation.target_id);
      const distance = Math.hypot(b.x - a.x, b.y - a.y) || 1;
      const dx = (b.x - a.x) / distance, dy = (b.y - a.y) / distance;
      const edge = svg('line', { x1: a.x + dx * 65, y1: a.y + dy * 35,
        x2: b.x - dx * 65, y2: b.y - dy * 35, stroke: '#91a79c', 'stroke-width': 2 });
      if (!['related_to', 'compares_with'].includes(relation.relation_type)) edge.setAttribute('marker-end', 'url(#artifact-arrow)');
      edge.append(svg('title', {}, tr('artifact.relation.' + relation.relation_type)));
      canvas.append(edge);
    }
    for (const object of artifact.objects) {
      const point = positions.get(object.id);
      const group = svg('g', { transform: `translate(${point.x - 115},${point.y - 40})`,
        role: 'button', tabindex: 0, 'aria-label': object.title,
        'aria-pressed': String(object.id === selected), 'data-object-id': object.id,
        class: 'artifact-node' + (object.id === selected ? ' selected' : '') });
      group.append(svg('rect', { width: 230, height: 80, rx: 12 }));
      group.append(svg('text', { x: 12, y: 23, class: 'artifact-kind' }, tr('artifact.kind.' + object.kind)));
      const title = Array.from(object.title);
      group.append(svg('text', { x: 12, y: 46 }, title.slice(0, 22).join('')));
      if (title.length > 22) group.append(svg('text', { x: 12, y: 65 }, title.slice(22, 43).join('') + (title.length > 43 ? '…' : '')));
      group.append(svg('title', {}, object.title));
      const focus = () => { selected = object.id; render(); };
      group.addEventListener('click', focus);
      group.addEventListener('keydown', event => {
        if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); focus(); }
      });
      canvas.append(group);
    }
    container.append(canvas);
  }
  function detail(container) {
    const object = objects.get(selected);
    container.append(node('h2', '', tr('artifact.keyInfo')));
    if (!object) { container.append(node('p', 'artifact-muted', tr('artifact.selectNode'))); return; }
    container.append(node('span', 'artifact-badge', tr('artifact.kind.' + object.kind)));
    container.append(node('h3', '', object.title));
    copy(container, object.summary);
    if (object.tags.length) container.append(node('p', 'artifact-muted', object.tags.map(tag => '#' + tag).join(' ')));
    source(container, object.source_url, tr('artifact.openSource'));
    if (Object.keys(object.metadata || {}).length) {
      const metadata = node('dl', 'artifact-metadata');
      for (const [key, value] of Object.entries(object.metadata)) {
        metadata.append(node('dt', '', tr('artifact.metadata.' + key)));
        metadata.append(node('dd', '', Array.isArray(value) ? value.join(', ') : String(value)));
      }
      container.append(metadata);
    }
    if (object.body_md) {
      const full = node('details', 'artifact-fulltext');
      full.append(node('summary', '', tr('artifact.fullText')));
      full.append(node('pre', 'artifact-original', object.body_md));
      container.append(full);
    }
    for (const relation of artifact.relations.filter(edge => edge.source_id === selected || edge.target_id === selected)) {
      const other = objects.get(relation.source_id === selected ? relation.target_id : relation.source_id);
      const section = node('section', 'artifact-relation');
      section.append(node('h3', '', tr('artifact.relationLine', {
        direction: ['related_to', 'compares_with'].includes(relation.relation_type) ? '↔' : relation.source_id === selected ? '→' : '←',
        type: tr('artifact.relation.' + relation.relation_type), title: other.title })));
      copy(section, relation.description);
      for (const evidence of relation.evidence) {
        const paragraph = node('div', 'artifact-evidence');
        paragraph.append(node('strong', '', tr('artifact.evidence')));
        if (evidence.evidence_object_id) paragraph.append(node('p', '', objects.get(evidence.evidence_object_id).title));
        if (evidence.locator) paragraph.append(node('p', '', evidence.locator));
        if (evidence.explanation) copy(paragraph, evidence.explanation);
        source(paragraph, evidence.source_url);
        section.append(paragraph);
      }
      container.append(section);
    }
  }
  function render() {
    if (options.languageSwitch !== false) { document.documentElement.lang = language === 'en' ? 'en' : 'zh-CN'; document.title = artifact.path.title + ' · ' + tr('artifact.badge'); }
    const content = node('article', 'artifact-doc');
    const header = node('header', 'artifact-header');
    if (options.languageSwitch !== false) {
      const select = node('select', 'artifact-language');
      select.setAttribute('aria-label', tr('artifact.language'));
      for (const locale of ['zh', 'en']) {
        const option = node('option', '', locale === 'zh' ? catalogs.zh['artifact.chinese'] : catalogs.en['artifact.english']);
        option.value = locale; option.selected = locale === language; select.append(option);
      }
      select.addEventListener('change', () => { language = select.value; render(); });
      header.append(select);
    }
    header.append(node('span', 'artifact-eyebrow', tr('artifact.badge')));
    header.append(node('h1', '', artifact.path.title));
    header.append(node('p', 'artifact-muted', tr('artifact.counts', {
      steps: artifact.path.steps.length, nodes: artifact.objects.length, relations: artifact.relations.length })));
    content.append(header);
    const overview = node('section', 'artifact-panel');
    overview.append(node('h2', '', tr('artifact.objective'))); copy(overview, artifact.path.objective_md);
    if (artifact.path.description_md) copy(overview, artifact.path.description_md);
    content.append(overview);
    const layout = node('div', 'artifact-layout');
    const graphPanel = node('section', 'artifact-panel');
    graphPanel.append(node('h2', '', tr('artifact.graph')));
    graphPanel.append(node('p', 'artifact-muted', tr('artifact.graphHelp')));
    const viewport = node('div', 'artifact-viewport'); graph(viewport); graphPanel.append(viewport);
    const inspector = node('section', 'artifact-panel artifact-inspector'); detail(inspector);
    layout.append(graphPanel, inspector); content.append(layout);
    const steps = node('section', 'artifact-panel'); steps.append(node('h2', '', tr('artifact.steps')));
    artifact.path.steps.forEach((step, index) => {
      const section = node('section', 'artifact-step');
      section.append(node('h3', '', tr('artifact.stepTitle', { number: index + 1, title: step.title })));
      if (step.estimated_minutes != null) section.append(node('p', 'artifact-muted', tr('artifact.minutes', { minutes: step.estimated_minutes })));
      copy(section, step.guidance_md);
      if (step.object_id) {
        const button = node('button', 'artifact-focus', tr('artifact.focusNode'));
        button.type = 'button'; button.addEventListener('click', () => {
          selected = step.object_id; render(); root.querySelector('.artifact-layout')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }); section.append(button);
      }
      if (step.completion_criteria_md) {
        const completion = node('div', 'artifact-completion');
        completion.append(node('strong', '', tr('artifact.completion'))); copy(completion, step.completion_criteria_md); section.append(completion);
      }
      steps.append(section);
    });
    content.append(steps);
    if (artifact.path.completion_criteria_md) {
      const finish = node('section', 'artifact-panel artifact-completion');
      finish.append(node('h2', '', tr('artifact.finish'))); copy(finish, artifact.path.completion_criteria_md); content.append(finish);
    }
    content.append(node('footer', 'artifact-footer', tr('artifact.snapshot', {
      date: new Date(artifact.created_at).toLocaleString(language === 'zh' ? 'zh-CN' : 'en-GB') })));
    root.replaceChildren(content);
  }
  render();
  return { setLanguage(next) { language = next === 'en' ? 'en' : 'zh'; render(); }, destroy() { root.replaceChildren(); } };
}

export const ARTIFACT_STYLES = `
.artifact-doc{font:14px/1.65 system-ui,"Segoe UI",sans-serif;color:#283f35;max-width:1200px;margin:auto;overflow-wrap:anywhere}
.artifact-doc *{box-sizing:border-box}.artifact-doc h1{font-size:30px;line-height:1.3;margin:12px 0}.artifact-doc h2{font-size:19px;margin:0 0 12px}.artifact-doc h3{font-size:15px;margin:12px 0 8px}
.artifact-header{padding:12px 0 20px}.artifact-eyebrow{font-size:11px;text-transform:uppercase;letter-spacing:2px;color:#477e62}.artifact-muted,.artifact-footer{color:#697d70;font-size:12px}
.artifact-panel{background:#fff;border:1px solid #dce5da;border-radius:14px;padding:24px;margin-bottom:20px;min-width:0}.artifact-layout{display:grid;grid-template-columns:minmax(0,1.6fr) minmax(260px,1fr);gap:20px}
.artifact-viewport{max-height:520px;overflow:auto;border-radius:10px;background:#f5f8f3}.artifact-graph{display:block;min-width:100%;max-width:none}.artifact-node{cursor:pointer;outline:none}.artifact-node rect{fill:#fff;stroke:#b4c8ba;stroke-width:1.5}.artifact-node.selected rect,.artifact-node:focus rect{stroke:#286349;stroke-width:3;fill:#edf6e9}.artifact-node text{font:12px system-ui;fill:#283f35}.artifact-node .artifact-kind{fill:#6d8474;font-size:10px}
.artifact-language{float:right;border:1px solid #b4c8ba;border-radius:7px;padding:7px;background:#fff;color:#283f35}.artifact-badge{display:inline-block;background:#e6f0e1;border-radius:5px;padding:3px 8px;font-size:11px}
.artifact-copy{white-space:pre-wrap;margin:8px 0}.artifact-source{display:block;color:#286349;text-decoration:underline;overflow-wrap:anywhere;margin:8px 0}.artifact-code,.artifact-original{white-space:pre-wrap;overflow-wrap:anywhere;background:#f4f6f1;padding:14px;border-radius:8px;font-size:12px;font-family:ui-monospace,monospace}
.artifact-step+.artifact-step,.artifact-relation{border-top:1px solid #e2e9df;margin-top:18px;padding-top:16px}.artifact-completion{border-left:3px solid #88ad8e;background:#f0f5ed;padding:12px 16px;border-radius:6px;margin-top:12px}.artifact-evidence{font-size:12px;background:#f6f8f3;padding:12px;border-radius:8px;margin-top:8px}.artifact-fulltext{margin-top:14px}.artifact-focus{background:#286349;color:white;border:0;padding:8px 12px;border-radius:7px;cursor:pointer}.artifact-footer{padding:8px 0 24px}
@media(max-width:760px){.artifact-layout{grid-template-columns:1fr;gap:0}.artifact-panel{padding:18px}.artifact-doc h1{font-size:24px}.artifact-viewport{max-height:350px}}
`;
