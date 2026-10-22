// Translate structured findings without translating user-authored titles or source URLs.
export function evidenceMessage(item, t, fallback) {
  if (!item.code || !item.params) return fallback(item.message);
  const values = {...item.params};
  for (const field of ['relation', 'claim', 'error', 'status']) {
    if (values[field]) values[field] = t(`health.${field}.${values[field]}`);
  }
  if (Array.isArray(values.missing)) values.missing = values.missing.map(field => t(`health.field.${field}`)).join(', ');
  if (item.code === 'link_dead') {
    const uses = [];
    if (values.objects) uses.push(t('health.sourceUses', {count:values.objects}));
    if (values.evidence) uses.push(t('health.evidenceUses', {count:values.evidence}));
    values.where = uses.join(', ');
  }
  return t(`health.finding.${item.code}`, values);
}
