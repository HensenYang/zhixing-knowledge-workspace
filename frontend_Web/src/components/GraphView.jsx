import { useEffect, useRef, useState } from 'react';
import cytoscape from 'cytoscape';
import { api } from '../services/api';
import { COLORS, RELATIONS, Empty, ErrorBox } from './shared';
export default function GraphView({
  center,
  depth = 1,
  filter = '',
  refresh = 0,
  onNode,
  onEdge,
  compact = false,
  relationType = '',
  direction = 'both',
  visitedIds = [],
  trailPairs = []
}) {
  const container = useRef(null);
  const [error, setError] = useState('');
  const [empty, setEmpty] = useState(false);
  const [summary, setSummary] = useState({nodes: 0, edges: 0, title: ''});
  const handlers = useRef({
    onNode,
    onEdge
  });
  handlers.current = {
    onNode,
    onEdge
  };
  const visitKey = JSON.stringify(visitedIds);
  const pathKey = JSON.stringify(trailPairs);
  useEffect(() => {
    let alive = true,
      graph;
    setError('');
    api(`/graph${center ? `?center=${center}&depth=${depth}` : ''}`).then(data => {
      if (!alive) return;
      let edges = data.edges.filter(edge => !relationType || edge.relation_type === relationType);
      const distances = new Map(center ? [[center, 0]] : []);
      if (center) {
        for (let level = 0; level < depth; level++) {
          const frontier = [...distances].filter(([, distance]) => distance === level).map(([id]) => id);
          for (const edge of edges) {
            const symmetric = ['related_to', 'compares_with'].includes(edge.relation_type);
            if ((symmetric || direction !== 'incoming') && frontier.includes(edge.source_id) && !distances.has(edge.target_id)) distances.set(edge.target_id, level + 1);
            if ((symmetric || direction !== 'outgoing') && frontier.includes(edge.target_id) && !distances.has(edge.source_id)) distances.set(edge.source_id, level + 1);
          }
        }
      }
      const nodes = data.nodes.filter(n => (!filter || n.kind === filter) && (!center || distances.has(n.id)));
      const visited = new Set(JSON.parse(visitKey));
      const pairs = JSON.parse(pathKey);
      const traversed = edge => pairs.some(([a, b]) => (edge.source_id === a && edge.target_id === b) || (edge.source_id === b && edge.target_id === a));
      const ids = new Set(nodes.map(n => n.id));
      setSummary({nodes: nodes.length, edges: edges.filter(e => ids.has(e.source_id) && ids.has(e.target_id)).length, title: nodes.find(n => n.id === center)?.title || ''});
      setEmpty(!nodes.length);
      graph = cytoscape({
        container: container.current,
        elements: [...nodes.map(n => ({
          classes: [n.id === center ? 'current' : '', visited.has(n.id) ? 'visited' : ''].join(' '),
          data: {
            id: n.id,
            label: n.title,
            color: COLORS[n.kind]
          }
        })), ...edges.filter(e => ids.has(e.source_id) && ids.has(e.target_id)).map(e => ({
          classes: traversed(e) ? 'traversed' : '',
          data: {
            id: e.id,
            source: e.source_id,
            target: e.target_id,
            label: RELATIONS[e.relation_type],
            directed: !['related_to', 'compares_with'].includes(e.relation_type)
          }
        }))],
        style: [{
          selector: 'node',
          style: {
            'background-color': 'data(color)',
            'label': 'data(label)',
            'font-size': compact ? 11 : 12,
            'font-family': 'sans-serif',
            'color': '#40534d',
            'text-valign': 'bottom',
            'text-margin-y': 9,
            'width': compact ? 22 : 32,
            'height': compact ? 22 : 32,
            'text-wrap': 'wrap',
            'text-max-width': 130,
            'border-width': 3,
            'border-color': '#ffffff'
          }
        }, {
          selector: 'edge',
          style: {
            'line-color': '#c6d1cb',
            'width': 1.5,
            'curve-style': 'bezier',
            'label': 'data(label)',
            'font-size': 10,
            'color': '#788a82',
            'text-background-color': '#f7f8f4',
            'text-background-opacity': 1,
            'text-background-padding': 3
          }
        }, {
          selector: 'edge[?directed]',
          style: {
            'target-arrow-shape': 'triangle',
            'target-arrow-color': '#bac9c0',
            'arrow-scale': 0.8
          }
        }, {
          selector: 'node.visited',
          style: { 'border-color': '#c4945e', 'border-width': 4 }
        }, {
          selector: 'edge.traversed',
          style: { 'line-color': '#c4945e', 'target-arrow-color': '#c4945e', 'width': 3 }
        }, {
          selector: 'node.current',
          style: { 'border-color': '#1b6b50', 'border-width': 6, 'width': compact ? 32 : 42, 'height': compact ? 32 : 42, 'font-weight': 'bold', 'color': '#1b6b50' }
        }, {
          selector: ':selected',
          style: {
            'border-color': '#1b6b50',
            'line-color': '#1b6b50',
            'target-arrow-color': '#1b6b50'
          }
        }],
        layout: compact && center ? { name: 'concentric', animate: false, concentric: node => 10 - (distances.get(node.id()) || 0), levelWidth: () => 1, minNodeSpacing: 65, nodeDimensionsIncludeLabels: true, padding: 25 } : {
          name: 'cose',
          animate: false,
          randomize: false,
          nodeDimensionsIncludeLabels: true,
          nodeRepulsion: () => 18000,
          idealEdgeLength: () => 160,
          componentSpacing: 120,
          nodeOverlap: 30,
          padding: 40
        },
        minZoom: 0.2,
        maxZoom: 3
      });
      if (graph.zoom() > 1.2) {
        graph.zoom(1.2);
        graph.center();
      }
      graph.on('tap', 'node', e => handlers.current.onNode?.(e.target.id()));
      graph.on('tap', 'edge', e => handlers.current.onEdge?.(e.target.id()));
      const resize = new ResizeObserver(() => {
        graph.resize();
      });
      resize.observe(container.current);
      graph.on('destroy', () => resize.disconnect());
    }).catch(e => {
      if (alive) setError(e.message);
    });
    return () => {
      alive = false;
      graph?.destroy();
    };
  }, [center, depth, filter, refresh, compact, relationType, direction, visitKey, pathKey]);
  return <div className={`graph-wrap ${compact ? 'compact' : ''}`}><div className="graph-container" role="img" aria-label={`${center ? `局部图谱，当前节点：${summary.title}` : '知识图谱'}，${summary.nodes}个节点，${summary.edges}条关系`} data-center={center || ''} data-node-count={summary.nodes} data-edge-count={summary.edges} ref={container} />{empty && <div className="graph-overlay"><Empty title="先建立几个知识对象">添加关系后，知识网络会在这里展开。</Empty></div>}<div className="graph-error"><ErrorBox message={error} /></div><span className="graph-hint">滚轮缩放 · 拖动节点 · 点击查看</span></div>;
}
