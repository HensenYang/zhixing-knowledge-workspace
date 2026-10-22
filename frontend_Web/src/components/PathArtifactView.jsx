import { useEffect, useRef } from 'react';
import { useLanguage } from '../i18n';
import zh from '../i18n/zh.json';
import en from '../i18n/en.json';
import { mountPathArtifact, ARTIFACT_STYLES } from '../artifacts/viewer';

export const artifactCatalogs = { zh, en };

export default function PathArtifactView({ artifact }) {
  const language = useLanguage();
  const root = useRef(null);
  const viewer = useRef(null);
  useEffect(() => {
    viewer.current = mountPathArtifact(root.current, artifact, artifactCatalogs, language, { languageSwitch: false });
    return () => { viewer.current?.destroy(); viewer.current = null; };
  }, [artifact]);
  // Keep the currently selected node when the surrounding interface changes language.
  useEffect(() => { viewer.current?.setLanguage(language); }, [language]);
  return <><style>{ARTIFACT_STYLES}</style><div className="path-artifact-view" ref={root} /></>;
}
