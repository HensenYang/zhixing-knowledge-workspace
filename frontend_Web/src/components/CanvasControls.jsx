import { Controls, ControlButton, useReactFlow, useStore, useStoreApi } from "@xyflow/react";
import { Plus, Minus, Maximize, Lock, Unlock } from "lucide-react";
import { t, useLanguage } from "../i18n";
export default function CanvasControls() {
  useLanguage();
  const {
    zoomIn,
    zoomOut,
    fitView
  } = useReactFlow();
  const store = useStoreApi();
  const interactive = useStore(state => state.nodesDraggable || state.nodesConnectable || state.elementsSelectable);
  const canZoomIn = useStore(state => state.transform[2] < state.maxZoom);
  const canZoomOut = useStore(state => state.transform[2] > state.minZoom);
  function toggleInteractivity() {
    store.setState({
      nodesDraggable: !interactive,
      nodesConnectable: !interactive,
      elementsSelectable: !interactive
    });
  }
  return <Controls showZoom={false} showFitView={false} showInteractive={false} aria-label={t("画布控制")}>
    <ControlButton onClick={() => zoomIn()} disabled={!canZoomIn} title={t("放大")} aria-label={t("放大")}><Plus /></ControlButton>
    <ControlButton onClick={() => zoomOut()} disabled={!canZoomOut} title={t("缩小")} aria-label={t("缩小")}><Minus /></ControlButton>
    <ControlButton onClick={() => fitView()} title={t("适应视图")} aria-label={t("适应视图")}><Maximize /></ControlButton>
    <ControlButton onClick={toggleInteractivity} title={t("切换交互")} aria-label={t("切换交互")}>{interactive ? <Unlock /> : <Lock />}</ControlButton>
  </Controls>;
}
