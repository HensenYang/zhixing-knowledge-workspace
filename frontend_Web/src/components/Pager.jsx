import {t,useLanguage} from '../i18n';
export default function Pager({total,limit,offset,onChange}) {
 useLanguage(); if(total<=limit)return null;
 const last=Math.min(offset+limit,total);
 return <nav className="pager" aria-label={t('分页')}><button type="button" className="ghost" disabled={offset<=0} onClick={()=>onChange(Math.max(0,offset-limit))}>{t('上一页')}</button><span role="status">{t('第 {first}–{last} 条，共 {total} 条',{first:offset+1,last,total})}</span><button type="button" className="ghost" disabled={last>=total} onClick={()=>onChange(offset+limit)}>{t('下一页')}</button></nav>;
}
