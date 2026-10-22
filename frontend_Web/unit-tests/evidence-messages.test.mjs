import {test} from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {createI18n} from '../src/i18n/runtime.js';
import {evidenceMessage} from '../src/services/evidenceMessages.js';

const catalogs=Object.fromEntries(['zh','en'].map(language=>[language,JSON.parse(fs.readFileSync(new URL(`../src/i18n/${language}.json`,import.meta.url),'utf8'))]));
test('structured evidence findings translate their labels, preserving user titles',()=>{
 const store=createI18n({catalogs});
 const finding={code:'relation_no_evidence',params:{source:'用户原始标题',relation:'uses',target:'Original target'}};
 assert.equal(evidenceMessage(finding,store.t,store.translateMessage),'《用户原始标题》使用《Original target》：没有任何证据。');
 store.setLanguage('en');
 assert.equal(evidenceMessage(finding,store.t,store.translateMessage),'用户原始标题 uses Original target: no evidence is recorded.');
 assert.equal(evidenceMessage({code:'run_incomplete',params:{experiment:'Experiment',status:'failed',missing:['command','git_commit']}},store.t,store.translateMessage),'A failed run of experiment Experiment is missing: command, code commit.');
});
