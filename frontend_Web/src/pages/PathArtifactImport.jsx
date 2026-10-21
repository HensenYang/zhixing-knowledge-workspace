import { useRef, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Download, Upload } from 'lucide-react';
import { t, msg, useLanguage } from '../i18n';
import { api } from '../services/api';
import { useAuth } from '../contexts/AuthContext';
import { ErrorBox, PageTitle } from '../components/shared';
import { announceChange } from '../components/RecordActions';
import LanguageSwitch from '../components/LanguageSwitch';
import PathArtifactView, { artifactCatalogs } from '../components/PathArtifactView';
import { ARTIFACT_MAX_BYTES, parsePathArtifact, downloadArtifact } from '../services/pathArtifacts';

export default function PathArtifactImport() {
  const language = useLanguage();
  const { user, workspace } = useAuth();
  const navigate = useNavigate();
  const generation = useRef(0);
  const [artifact, setArtifact] = useState(null);
  const [fileName, setFileName] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const canSave = user && ['owner', 'editor'].includes(workspace?.role);

  async function inspect(file) {
    const current = ++generation.current;
    setArtifact(null); setError(''); setFileName(file?.name || '');
    if (!file) return;
    if (file.size > ARTIFACT_MAX_BYTES) { setError(msg('artifact.tooLarge')); return; }
    try {
      const value = parsePathArtifact(await file.text());
      if (current === generation.current) setArtifact(value);
    } catch (failure) { if (current === generation.current) setError(failure.message); }
  }
  async function save() {
    setBusy(true); setError('');
    try {
      const data = new FormData();
      data.append('file', new File([JSON.stringify(artifact)], 'learning-path.json', { type: 'application/json' }));
      const saved = await api('/learning-paths/import', { method: 'POST', body: data });
      announceChange(); navigate(`/paths/${saved.id}`);
    } catch (failure) { setError(failure.message); }
    finally { setBusy(false); }
  }
  function download(format) {
    try { downloadArtifact(artifact, format, artifactCatalogs, language); }
    catch (failure) { setError(failure.message); }
  }
  return <main className="public-path-shell artifact-import-page">
    <div className="artifact-page-toolbar"><Link to="/paths">{t('返回路径列表')}</Link><LanguageSwitch /></div>
    <PageTitle eyebrow={t('artifact.badge')} title={t('artifact.importTitle')}>{t('artifact.importIntro')}</PageTitle>
    <section className="panel artifact-transfer-panel">
      <label className="file-upload"><Upload size={18} /><span>{fileName || t('artifact.chooseFile')}</span>
        <input type="file" accept=".json,.html,application/json,text/html" aria-label={t('artifact.chooseFile')} disabled={busy}
          onChange={event => inspect(event.target.files[0])} /></label>
      <p className="muted">{t('artifact.localPreview')}</p>
      <p className="muted">{t('artifact.scope')}</p>
      <ErrorBox message={error} />
      {artifact && <>
        <p>{t('artifact.importCounts', { steps: artifact.path.steps.length, nodes: artifact.objects.length, relations: artifact.relations.length })}</p>
        <p className="info-note">{t('artifact.independentCopy')}</p>
        <div className="actions">
          <button onClick={save} disabled={!canSave || busy}>{busy ? t('处理中…') : t('artifact.saveCopy')}</button>
          <button className="ghost" onClick={() => download('json')} disabled={busy}><Download size={15} />{t('artifact.downloadJson')}</button>
          <button className="ghost" onClick={() => download('html')} disabled={busy}><Download size={15} />{t('artifact.downloadHtml')}</button>
        </div>
        {!user && <p><Link className="text-link" to="/">{t('artifact.loginToSave')}</Link></p>}
        {user && !canSave && <p className="muted">{t('artifact.readOnlyRole')}</p>}
      </>}
    </section>
    {artifact && <PathArtifactView artifact={artifact} />}
  </main>;
}
