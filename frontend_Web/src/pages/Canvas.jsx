import CanvasControls from "../components/CanvasControls";
import { t, msg, useLanguage } from "../i18n";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ReactFlow, Background, MiniMap, Handle, Position, applyNodeChanges, applyEdgeChanges } from "@xyflow/react";
import { Plus, Save, Undo2, Redo2, Group, StickyNote, Trash2 } from "lucide-react";
import { api, write } from "../services/api";
import useDraft from "../hooks/useDraft";
import { PageTitle, Field, Badge, Empty, ErrorBox, RELATIONS } from "../components/shared";
import { DeleteButton, useWorkspaceChanges } from "../components/RecordActions";
export function CanvasList() {
  useLanguage();
  const [canvases, setCanvases] = useState([]),
    [title, setTitle] = useState(""),
    [error, setError] = useState("");
  const navigate = useNavigate();
  const load = () => api("/canvases").then(setCanvases).catch(e => setError(e.message));
  useEffect(() => {
    load();
  }, []);
  useWorkspaceChanges(load);
  async function create(e) {
    e.preventDefault();
    try {
      const c = await write("/canvases", {
        title: title || t("我的研究画布")
      });
      navigate(`/canvases/${c.id}`);
    } catch (e) {
      setError(e.message);
    }
  }
  return <><PageTitle eyebrow={t("THINKING CANVAS")} title={t("自由画布")}>{t("围绕一个问题编排知识。同一份笔记可以出现在多个画布。")}</PageTitle><form className="toolbar" onSubmit={create}><input aria-label={t("新画布名称")} value={title} onChange={e => setTitle(e.target.value)} placeholder={t("例如：VLA 与世界模型如何配合？")} /><button><Plus size={16} />{t("新建画布")}</button></form><ErrorBox message={error} /><div className="knowledge-grid">{canvases.map(c => <article className="knowledge-card canvas-card" key={c.id}><div className="canvas-motif"><i /><i /><i /></div><h3>{c.title}</h3><p>{t("打开画布，继续连接与整理。")}</p><div className="actions"><Link className="button ghost" to={`/canvases/${c.id}`}>{t("编辑画布")}</Link><button className="ghost" onClick={async () => {
            const title = window.prompt(t("画布名称"), c.title);
            if (!title?.trim()) return;
            try {
              await write(`/canvases/${c.id}`, {
                title: title.trim(),
                version: c.version
              }, "PATCH");
              await load();
            } catch (e) {
              setError(e.message);
            }
          }}>{t("重命名")}</button><DeleteButton kind="canvas" id={c.id} title={c.title} /></div></article>)}</div>{!canvases.length && !error && <Empty title={t("创建你的第一个研究画布")} />}</>;
}
function KnowledgeNode({
  data,
  selected
}) {
  useLanguage();
  return <div className={`flow-card ${selected ? "selected" : ""}`}><Handle type="target" position={Position.Left} />{data.kind && <Badge kind={data.kind} />}<strong>{data.title}</strong>{data.summary && <p>{data.summary}</p>}<Handle type="source" position={Position.Right} /></div>;
}
const nodeTypes = {
  knowledge: KnowledgeNode
};
function documentValue(c) {
  return {
    title: c.title,
    version: c.version,
    viewport: c.viewport,
    items: c.items.map(({
      id,
      item_type,
      object_id,
      parent_id,
      x,
      y,
      width,
      height,
      properties
    }) => ({
      id,
      item_type,
      object_id,
      parent_id,
      x,
      y,
      width,
      height,
      properties
    })),
    edges: c.edges.map(({
      id,
      source_item_id,
      target_item_id,
      relation_id,
      label,
      properties
    }) => ({
      id,
      source_item_id,
      target_item_id,
      relation_id,
      label,
      properties
    }))
  };
}
export function CanvasEditor() {
  useLanguage();
  const {
    id
  } = useParams();
  return <CanvasEditorInner key={id} id={id} />;
}
function CanvasEditorInner({
  id
}) {
  const language = useLanguage();
  const navigate = useNavigate();
  const [initial, setInitial] = useState(null),
    [objects, setObjects] = useState([]),
    [activeRelations, setActiveRelations] = useState(null),
    [q, setQ] = useState(""),
    [selected, setSelected] = useState([]),
    [edgeId, setEdgeId] = useState(""),
    [error, setError] = useState(""),
    [history, setHistory] = useState(null),
    [type, setType] = useState("related_to"),
    [description, setDescription] = useState("");
  const flow = useRef(null),
    past = useRef([]),
    future = useRef([]),
    dragBefore = useRef(null);
  const [, force] = useState(0);
  useEffect(() => {
    api(`/canvases/${id}`).then(c => setInitial(documentValue(c))).catch(e => setError(e.message));
    const load = () => Promise.all([api("/objects?limit=1000&archived=true"), api("/relations")]).then(([objects, relations]) => {
      setObjects(objects);
      setActiveRelations(new Set(relations.map(r => r.id)));
    }).catch(e => setError(e.message));
    load();
    const timer = setInterval(load, 10000);
    return () => clearInterval(timer);
  }, [id]);
  const draft = useDraft(`canvas:${id}`, initial, v => write(`/canvases/${id}/document`, v, "PUT").then(documentValue));
  useWorkspaceChanges(() => Promise.all([api("/objects?limit=1000&archived=true"), api("/relations")]).then(([o, r]) => {
    setObjects(o);
    setActiveRelations(new Set(r.map(item => item.id)));
  }).catch(e => setError(e.message)));
  const doc = draft.value;
  const objectMap = useMemo(() => Object.fromEntries(objects.map(o => [o.id, o])), [objects, language]);
  const remember = () => {
    if (doc) {
      past.current = [...past.current, structuredClone(doc)].slice(-40);
      future.current = [];
      force(x => x + 1);
    }
  };
  const modify = (fn, record = true) => {
    if (record) remember();
    draft.change(v => fn(v));
  };
  const nodes = useMemo(() => {
    if (!doc) return [];
    const ordered = [],
      remaining = [...doc.items];
    let count = remaining.length + 1;
    while (remaining.length && count--) {
      const index = remaining.findIndex(i => !i.parent_id || ordered.some(n => n.id === i.parent_id));
      if (index < 0) break;
      const [item] = remaining.splice(index, 1);
      const o = objectMap[item.object_id];
      ordered.push({
        id: item.id,
        type: item.item_type === "group" ? "group" : "knowledge",
        position: {
          x: item.x,
          y: item.y
        },
        parentId: item.parent_id || undefined,
        width: item.width,
        height: item.height,
        measured: {
          width: item.width,
          height: item.height
        },
        style: {
          width: item.width,
          height: item.height,
          ...(item.item_type === "group" ? {
            background: "#e8eee880",
            border: "1px dashed #a3b4a6",
            borderRadius: 16
          } : {})
        },
        selected: selected.includes(item.id),
        data: {
          label: item.properties.text,
          title: item.item_type === "object" ? o?.title || t("知识对象已删除 · 可在回收站恢复") : item.properties.text || t("自由笔记"),
          kind: o?.kind,
          summary: item.item_type === "group" ? "" : o?.summary
        }
      });
    }
    return ordered;
  }, [doc, objectMap, selected, language]);
  const edges = useMemo(() => doc?.edges.map(e => ({
    id: e.id,
    source: e.source_item_id,
    target: e.target_item_id,
    label: (e.label || (e.relation_id ? t("知识关系") : t("局部连线"))) + (e.relation_id && activeRelations && !activeRelations.has(e.relation_id) ? t(" · 已删除") : ""),
    selected: e.id === edgeId,
    style: {
      stroke: e.relation_id && (!activeRelations || activeRelations.has(e.relation_id)) ? "#4d886d" : "#a9b7ad",
      strokeWidth: 1.7
    },
    data: {
      relation_id: e.relation_id
    }
  })) || [], [doc, edgeId, activeRelations, language]);
  const onNodesChange = useCallback(changes => {
    if (!doc) return;
    const selections = changes.filter(c => c.type === "select");
    if (selections.length) {
      setSelected(previous => {
        const ids = new Set(previous);
        for (const change of selections) {
          if (change.selected) ids.add(change.id);else ids.delete(change.id);
        }
        return Array.from(ids);
      });
      if (selections.some(c => c.selected)) setEdgeId("");
    }
    const changesToApply = changes.filter(c => c.type !== "select" && c.type !== "dimensions");
    if (!changesToApply.length) return;
    const changed = applyNodeChanges(changesToApply, nodes);
    const ids = new Set(changed.map(n => n.id));
    modify(v => ({
      ...v,
      items: v.items.filter(i => ids.has(i.id)).map(i => {
        const n = changed.find(n => n.id === i.id);
        return {
          ...i,
          x: n.position.x,
          y: n.position.y
        };
      }),
      edges: v.edges.filter(e => ids.has(e.source_item_id) && ids.has(e.target_item_id))
    }), false);
  }, [doc, nodes]);
  function onEdgesChange(changes) {
    if (!doc) return;
    const selection = changes.find(c => c.type === "select" && c.selected);
    if (selection) {
      setEdgeId(selection.id);
      setSelected([]);
    } else if (changes.some(c => c.type === "select" && !c.selected && c.id === edgeId)) {
      setEdgeId("");
    }
    const removed = new Set(changes.filter(c => c.type === "remove").map(c => c.id));
    if (removed.size) modify(v => ({
      ...v,
      edges: v.edges.filter(e => !removed.has(e.id))
    }));
  }
  function addObject(objectId, position) {
    const offset = doc.items.length * 18;
    modify(v => ({
      ...v,
      items: [...v.items, {
        id: crypto.randomUUID(),
        item_type: "object",
        object_id: objectId,
        parent_id: null,
        x: position?.x ?? 80 + offset,
        y: position?.y ?? 80 + offset,
        width: 260,
        height: 155,
        properties: {}
      }]
    }));
  }
  function addText() {
    modify(v => ({
      ...v,
      items: [...v.items, {
        id: crypto.randomUUID(),
        item_type: "text",
        object_id: null,
        parent_id: null,
        x: 120,
        y: 120,
        width: 260,
        height: 150,
        properties: {
          text: t("写下一个想法…")
        }
      }]
    }));
  }
  function connect(connection) {
    modify(v => ({
      ...v,
      edges: [...v.edges, {
        id: crypto.randomUUID(),
        source_item_id: connection.source,
        target_item_id: connection.target,
        relation_id: null,
        label: t("局部连线"),
        properties: {}
      }]
    }));
  }
  function undo() {
    if (!past.current.length) return;
    future.current.push(structuredClone(doc));
    const old = past.current.pop();
    draft.change({
      ...old,
      version: doc.version
    });
    force(x => x + 1);
  }
  function redo() {
    if (!future.current.length) return;
    past.current.push(structuredClone(doc));
    const next = future.current.pop();
    draft.change({
      ...next,
      version: doc.version
    });
    force(x => x + 1);
  }
  function group() {
    const items = doc.items.filter(i => selected.includes(i.id) && !i.parent_id && i.item_type !== "group");
    if (items.length < 2) {
      setError(msg("请选择至少两张未分组卡片（按住 Shift 框选）。"));
      return;
    }
    const x = Math.min(...items.map(i => i.x)) - 25,
      y = Math.min(...items.map(i => i.y)) - 45;
    const id = crypto.randomUUID();
    modify(v => ({
      ...v,
      items: [{
        id,
        item_type: "group",
        object_id: null,
        parent_id: null,
        x,
        y,
        width: Math.max(...items.map(i => i.x + i.width)) - x + 25,
        height: Math.max(...items.map(i => i.y + i.height)) - y + 25,
        properties: {
          text: t("知识分组")
        }
      }, ...v.items.map(i => items.some(a => a.id === i.id) ? {
        ...i,
        parent_id: id,
        x: i.x - x,
        y: i.y - y
      } : i)]
    }));
    setError("");
  }
  function ungroup(groupId) {
    const group = doc.items.find(i => i.id === groupId);
    modify(v => ({
      ...v,
      items: v.items.filter(i => i.id !== groupId).map(i => i.parent_id === groupId ? {
        ...i,
        parent_id: null,
        x: i.x + group.x,
        y: i.y + group.y
      } : i),
      edges: v.edges.filter(e => e.source_item_id !== groupId && e.target_item_id !== groupId)
    }));
  }
  function remove() {
    const groups = doc.items.filter(i => selected.includes(i.id) && i.item_type === "group");
    if (groups.length) {
      setError(msg("请先解除分组，再删除卡片。"));
      return;
    }
    modify(v => ({
      ...v,
      items: v.items.filter(i => !selected.includes(i.id)),
      edges: v.edges.filter(e => !selected.includes(e.source_item_id) && !selected.includes(e.target_item_id) && e.id !== edgeId)
    }));
    setSelected([]);
    setEdgeId("");
  }
  const selectedItem = doc?.items.find(i => i.id === selected[0]),
    selectedEdge = doc?.edges.find(e => e.id === edgeId);
  async function promote() {
    const source = doc.items.find(i => i.id === selectedEdge.source_item_id),
      target = doc.items.find(i => i.id === selectedEdge.target_item_id);
    if (!source?.object_id || !target?.object_id) {
      setError(msg("只有两张知识对象卡片之间的连线可以提升为知识关系。"));
      return;
    }
    try {
      const relation = await write("/relations", {
        source_id: source.object_id,
        target_id: target.object_id,
        relation_type: type,
        description
      });
      modify(v => ({
        ...v,
        edges: v.edges.map(e => e.id === edgeId ? {
          ...e,
          relation_id: relation.id,
          label: t(RELATIONS[type])
        } : e)
      }));
      setError("");
    } catch (e) {
      setError(e.message);
    }
  }
  if (!doc) return <><ErrorBox message={error} /><div className="empty">{t("加载画布…")}</div></>;
  return <div className="canvas-editor-page"><div className="canvas-top"><div><Link to="/canvases" className="text-link">{t("← 画布")}</Link><input aria-label={t("画布标题")} value={doc.title} onChange={e => modify(v => ({
          ...v,
          title: e.target.value
        }), false)} /></div><div className="actions"><span className="save-status">{draft.status}</span><button className="icon-button" aria-label={t("撤销")} disabled={!past.current.length} onClick={undo}><Undo2 size={17} /></button><button className="icon-button" aria-label={t("重做")} disabled={!future.current.length} onClick={redo}><Redo2 size={17} /></button><button onClick={draft.save}><Save size={15} />{t("保存画布")}</button><DeleteButton kind="canvas" id={id} title={doc.title} label={t("删除画布")} beforeDelete={draft.save} onDeleted={() => navigate("/canvases")} /></div></div><ErrorBox message={error || draft.error} />{draft.error && <div className="actions"><button onClick={draft.download}>{t("下载草稿")}</button><button className="ghost" onClick={async () => {
        await draft.discard();
        setInitial(documentValue(await api(`/canvases/${id}`)));
      }}>{t("放弃草稿并重新加载")}</button></div>}<div className="canvas-layout"><aside className="canvas-library"><span className="eyebrow">{t("KNOWLEDGE CARDS")}</span><h3>{t("拖入知识")}</h3><input aria-label={t("搜索画布知识")} placeholder={t("搜索笔记…")} value={q} onChange={e => setQ(e.target.value)} /><div className="canvas-library-list">{objects.filter(o => !o.archived_at && o.title.toLowerCase().includes(q.toLowerCase())).map(o => <button key={o.id} draggable onDragStart={e => e.dataTransfer.setData("application/knowledge-object", o.id)} onClick={() => addObject(o.id)} className="library-object"><Badge kind={o.kind} /><span>{o.title}</span></button>)}</div><button className="ghost" onClick={addText}><StickyNote size={15} />{t("自由文本卡片")}</button><button className="ghost" onClick={group}><Group size={15} />{t("组合选中卡片")}</button><button className="ghost danger" onClick={remove}><Trash2 size={15} />{t("移除选中元素")}</button><button className="ghost" onClick={async () => {
          try {
            setHistory(await api(`/canvases/${id}/revisions`));
          } catch (e) {
            setError(e.message);
          }
        }}>{t("查看保存历史")}</button></aside><section className="canvas-surface"><ReactFlow nodes={nodes} edges={edges} nodeTypes={nodeTypes} defaultViewport={doc.viewport} onInit={instance => {
          flow.current = instance;
        }} onNodesChange={onNodesChange} onEdgesChange={onEdgesChange} onConnect={connect} onPaneClick={() => {
          setSelected([]);
          setEdgeId("");
        }} onEdgeClick={(_, edge) => {
          setEdgeId(edge.id);
          setSelected([]);
        }} onNodeDragStart={() => {
          dragBefore.current = structuredClone(doc);
        }} onNodeDragStop={() => {
          if (dragBefore.current) {
            past.current = [...past.current, dragBefore.current].slice(-40);
            future.current = [];
            dragBefore.current = null;
            force(x => x + 1);
          }
        }} onMoveEnd={(_, viewport) => {
          if (JSON.stringify(viewport) !== JSON.stringify(doc.viewport)) modify(v => ({
            ...v,
            viewport
          }), false);
        }} onDrop={e => {
          e.preventDefault();
          const objectId = e.dataTransfer.getData("application/knowledge-object");
          if (objectId && flow.current) addObject(objectId, flow.current.screenToFlowPosition({
            x: e.clientX,
            y: e.clientY
          }));
        }} onDragOver={e => {
          e.preventDefault();
          e.dataTransfer.dropEffect = "copy";
        }} deleteKeyCode={null} minZoom={0.15} maxZoom={2.5} selectionOnDrag multiSelectionKeyCode="Shift" panOnDrag={[1, 2]}><Background color="#c9d2c8" gap={24} size={1} /><CanvasControls /><MiniMap ariaLabel={t("小地图")} pannable zoomable nodeColor="#b3cbbd" /></ReactFlow><span className="canvas-tip">{t("拖动卡片端点建立连接 · Shift 框选 · 鼠标中键移动画布")}</span></section><aside className="canvas-inspector">{selectedEdge ? <><h3>{t("连线属性")}</h3><Field label={t("显示文字")}><input value={selectedEdge.label} onChange={e => modify(v => ({
              ...v,
              edges: v.edges.map(edge => edge.id === edgeId ? {
                ...edge,
                label: e.target.value
              } : edge)
            }), false)} /></Field><p className="muted">{selectedEdge.relation_id ? t("此连线引用正式知识关系。移除画布连线不删除知识关系。") : t("此连线只用于当前画布的思考和整理。")}</p>{!selectedEdge.relation_id && <><Field label={t("提升为知识关系")}><select value={type} onChange={e => setType(e.target.value)}>{Object.entries(RELATIONS).map(([k, v]) => <option key={k} value={k}>{t(v)}</option>)}</select></Field><Field label={t("联系说明")}><textarea value={description} onChange={e => setDescription(e.target.value)} rows={4} /></Field><button onClick={promote}>{t("保存为知识关系")}</button></>}<button className="ghost danger" onClick={() => modify(v => ({
            ...v,
            edges: v.edges.filter(e => e.id !== edgeId)
          }))}>{t("移除画布连线")}</button></> : selectedItem ? <><h3>{selectedItem.item_type === "group" ? t("知识分组") : t("卡片详情")}</h3>{selectedItem.object_id ? <>{objectMap[selectedItem.object_id] && <Badge kind={objectMap[selectedItem.object_id].kind} />}<h3>{objectMap[selectedItem.object_id]?.title}</h3>{objectMap[selectedItem.object_id] && <Link className="text-link" to={`/knowledge/${selectedItem.object_id}`}>{t("修改原始笔记 ↗")}</Link>}{objectMap[selectedItem.object_id] && <DeleteButton kind="object" id={selectedItem.object_id} title={objectMap[selectedItem.object_id].title} label={t("删除知识对象")} beforeDelete={draft.save} />}<p className="muted">{t("内容引用原始笔记，位置属于当前画布。")}</p></> : <Field label={t("文本")}><textarea value={selectedItem.properties.text || ""} rows={6} onChange={e => modify(v => ({
              ...v,
              items: v.items.map(i => i.id === selectedItem.id ? {
                ...i,
                properties: {
                  ...i.properties,
                  text: e.target.value
                }
              } : i)
            }), false)} /></Field>}{selectedItem.item_type === "group" && <button className="ghost" onClick={() => ungroup(selectedItem.id)}>{t("解除分组")}</button>}</> : <><span className="eyebrow">{t("FREE ARRANGEMENT")}</span><h3>{t("围绕问题整理思路")}</h3><p className="muted">{t("左侧点击或拖入知识卡片。选择卡片或连线，在这里修改。")}</p><div className="info-note">{t("局部连线与知识关系分开保存，你可以自由探索尚未验证的联系。")}</div></>}{history && <div className="history"><h3>{t("保存历史")}</h3>{history.slice(0, 10).map(r => <button className="relation-row" key={r.id} onClick={() => {
            remember();
            draft.change({
              ...documentValue(r.snapshot),
              version: doc.version
            });
            setHistory(null);
          }}>{t("版本 {version} · 恢复到草稿", {
              version: r.version
            })}</button>)}</div>}</aside></div></div>;
}
