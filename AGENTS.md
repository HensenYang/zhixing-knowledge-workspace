# Repository instructions

## Bilingual interface

- Every new or changed user-facing interface message must support Chinese and English in the same change. This includes navigation, headings, buttons, form labels, placeholders, statuses, dialogs, empty states, validation messages, and accessibility labels.
- Use `t(key, values)` from `frontend_Web/src/i18n` at render time. Subscribe with `useLanguage()` in components using translated text; include the language in memo/effect dependencies when translated labels are cached or drawn by a graph library.
- Add matching entries to both `frontend_Web/src/i18n/zh.json` and `en.json`. Keep placeholder names identical. Use complete sentences with placeholders instead of joining translated sentence fragments.
- Use `msg(key)` for module-level label maps or messages stored in state, then translate at render time. Use `translateMessage()` for system errors. Add both translations for any new backend error displayed in the UI.
- Preserve user-authored notes, titles, tags, attachments, research material, commands, and model responses. Changing interface language must not translate or overwrite those values, reset forms, navigate, or discard drafts.
- Do not store localized display labels as API enum values. Keep the existing database and API identifiers stable.
- Run `npm run check:i18n`, `npm run test:i18n`, and `npm run build` from `frontend_Web`. Use `tests/i18n-language.spec.js` for browser verification against mocked APIs. Do not run database-writing tests against a personal database.

See [the localization guide](docs/i18n.md) for examples.
