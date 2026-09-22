'use strict';
const $ = id => document.getElementById(id);
const el = (tag, text, cls) => { const n = document.createElement(tag); if (text !== undefined) n.textContent = text; if (cls) n.className = cls; return n; };
const fragment = new URLSearchParams(location.hash.slice(1));
let token = fragment.get('token') || sessionStorage.getItem('ranuSession') || '';
if (fragment.has('token')) { sessionStorage.setItem('ranuSession', token); history.replaceState(null, '', '/'); }
let state = null, currentView = 'registry', selection = new Set(), formContext = null, pendingPreview = null;
const labels = {licenseId:'License ID',gameName:'Game name',universeId:'Universe ID',groupId:'Group ID',grantor:'Grantor',basis:'Permission basis',agreementId:'Agreement reference',operatorAcceptanceRecorded:'Acceptance recorded',startsAt:'Starts at · UTC',duration:'Duration',expiresAt:'Expires at · UTC',revocableAtWill:'At-will revocation',registryRemovalTerminatesPermission:'Removal ends permission',registryStatus:'Listing',grantReference:'Grant reference',scopeReference:'Scope reference',terminationTermsReference:'Revocation / termination terms',permissionState:'Recorded state',statusEffectiveAt:'Ending effective · UTC',statusReference:'Ending reference'};
const baseFields = ['licenseId','gameName','universeId','groupId','basis','grantor','agreementId','operatorAcceptanceRecorded','startsAt','expiresAt','duration','revocableAtWill','registryRemovalTerminatesPermission','registryStatus','grantReference','scopeReference','terminationTermsReference'];
const nullableFields = ['agreementId','grantReference','scopeReference','terminationTermsReference'];
const dateLabels = {'within-term':'Within recorded term','expiring':'Expiring soon','expired':'Past recorded expiry','not-started':'Not started','ending-recorded':'Ending recorded','ending-future':'Ending dated in future'};

async function api(path, payload) {
  const response = await fetch(path, {method:payload === undefined ? 'GET':'POST',headers:{Authorization:'Bearer '+token,...(payload === undefined?{}:{'Content-Type':'application/json'})},body:payload === undefined?undefined:JSON.stringify(payload),cache:'no-store'});
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || 'Local request failed.');
  return data;
}
function notice(message, bad=false) { $('notice').textContent=message; $('notice').className=bad?'bad':''; $('notice').hidden=false; }
async function refresh(announce=false) {
  try {
    const fresh = await api('/api/state'); state=fresh;
    selection = new Set([...selection].filter(id=>state.records.some(r=>r.licenseId===id)));
    render();
    if (announce) notice('Reloaded from disk. No records were changed.');
  } catch(e) { notice(e.message,true); }
}
function button(text, fn, cls='small') { const b=el('button',text,cls); b.type='button'; b.addEventListener('click',fn); return b; }
function badge(text, cls='') { return el('span',text,'badge '+cls); }
function dateDisplay(value) { return value?value.replace('T',' ').replace('Z',' UTC'):'No scheduled expiry'; }
function showView(view) {
  currentView=view;
  for (const key of ['registry','history','workspace']) $(key+'-view').hidden=key!==view;
  document.querySelectorAll('.nav').forEach(n=>n.classList.toggle('active',n.dataset.view===view));
  $('page-title').textContent={registry:'Game registry',history:'Activity & recovery',workspace:'Files & tools'}[view];
  $('page-subtitle').textContent={registry:'A clear view of your recorded permissions.',history:'A private trail of changes, with recovery when you need it.',workspace:'Manage local copies and export records for publishing.'}[view];
}
function visibleRecords() {
  const query=$('search').value.trim().toLowerCase(), filter=$('filter').value;
  return state.records.filter(r=>(!query || [r.gameName,r.licenseId,r.universeId,r.groupId].join(' ').toLowerCase().includes(query)) && (filter==='all'||(filter==='archived'?r.registryStatus==='archived':filter==='perpetual'?r.duration==='perpetual':r.dateState===filter)));
}
function render() {
  if (!state) return;
  $('schema').textContent=state.schemaVersion;
  const metrics=[['Total records',state.summary.total,'Across your registry',''],['Expiring in 30 days',state.summary.expiring,'By the recorded UTC dates','warn'],['Past recorded expiry',state.summary.expired,'Review before renewing','alert'],['Archived listings',state.summary.archived,'Administrative status only','']];
  $('metrics').replaceChildren(...metrics.map(([title,count,note,cls])=>{const card=el('div',undefined,'metric '+cls);card.append(el('div',title,'metric-label'),el('div',String(count),'metric-number'),el('div',note,'metric-note'));return card;}));
  renderRecords();renderHistory();renderFiles();
}
function renderRecords() {
  if(!state)return;
  const rows=visibleRecords(); $('result-count').textContent=rows.length+' of '+state.records.length+' records';
  $('records').replaceChildren(...rows.map(r=>{
    const tr=el('tr'), checkCell=el('td'), check=document.createElement('input');check.type='checkbox';check.checked=selection.has(r.licenseId);check.setAttribute('aria-label','Select '+r.gameName);check.addEventListener('change',()=>{check.checked?selection.add(r.licenseId):selection.delete(r.licenseId);renderRecords();});checkCell.append(check);
    const nameCell=el('td'), game=el('div',undefined,'game-cell'), avatar=el('span',(r.gameName[0]||'G').toUpperCase(),'game-avatar'), title=el('div');title.append(el('div',r.gameName,'game-name'),el('div',r.licenseId+' · '+r.universeId,'game-meta'));game.append(avatar,title);nameCell.append(game);
    const term=el('td');term.append(badge(dateLabels[r.dateState],['expired','ending-recorded'].includes(r.dateState)?'red':r.dateState==='expiring'?'amber':'green'),el('span',r.duration==='perpetual'?'No scheduled expiry':'Fixed term','term-sub'));
    const date=el('td');date.append(el('div',r.expiresAt?r.expiresAt.slice(0,10):'—'),el('span',r.expiresAt?r.expiresAt.slice(11,19)+' UTC':'Perpetual term','term-sub'));
    const listing=el('td');listing.append(badge(r.registryStatus==='listed'?'Listed':'Archived'));
    const action=el('td');action.append(button('Manage →',()=>detail(r)));
    tr.append(checkCell,nameCell,term,date,listing,action);return tr;
  }));
  $('empty').hidden=rows.length!==0;
  $('bulk').hidden=selection.size===0;$('selected-count').textContent=selection.size+' selected';
  $('select-all').checked=rows.length>0&&rows.every(r=>selection.has(r.licenseId));
  $('select-all').indeterminate=rows.some(r=>selection.has(r.licenseId))&&!$('select-all').checked;
}
function renderHistory(){
  $('history-list').replaceChildren(...state.history.map(e=>{const row=el('div',undefined,'activity'),info=el('div');info.append(el('h3',e.action.replace(/^web-/,'').replaceAll('-',' ')),el('p',e.recordedAt+' · '+(e.changedLicenseIds||[]).join(', ')));row.append(info,button('View audit',async()=>{try{$('event-content').textContent=JSON.stringify(await api('/api/history/'+encodeURIComponent(e.eventId)),null,2);$('event-dialog').showModal();}catch(err){notice(err.message,true);}}));return row;}));
  if(state.historyTotal>100)$('history-list').append(el('p','Showing the latest 100 events; complete history remains in the private audit directory.','muted'));
  $('removed-list').replaceChildren(...state.removed.map(r=>{const row=el('div',undefined,'activity'),info=el('div');info.append(el('h3',r.gameName),el('p',r.licenseId+' · '+r.universeId));row.append(info,button('Recover row',()=>openForm('recover',r)));return row;}));
}
function renderFiles(){
  const entries=[['Canonical registry',state.registryPath],['Private audit & backups',state.privatePath],['Private mirror',state.mirrorPath||'Not configured. Launch with --mirror "path/to/licenses.json".'],['Mirror status',state.mirrorState]];
  $('paths').replaceChildren(...entries.flatMap(([key,value])=>[el('dt',key),el('dd',value)]));
  $('mirror').disabled=!state.mirrorPath;
}
function detail(r){
  $('detail-id').textContent=r.licenseId;$('detail-name').textContent=r.gameName;
  const dl=el('dl',undefined,'details-grid');
  for(const key of [...baseFields,'permissionState','statusEffectiveAt','statusReference']){const item=el('div');item.append(el('dt',labels[key]),el('dd',r[key]===null?'Not specified':String(r[key])));dl.append(item);}
  $('detail-body').replaceChildren(el('div',r.dateDescription+'. Listing changes do not alter permission.','details-note'),dl);
  const actions=[['Edit / amend','edit'],['Extend expiry','extend'],['Record ending','end'],['Give permission again','regrant'],[r.registryStatus==='archived'?'Unarchive listing':'Archive listing',r.registryStatus==='archived'?'unarchive':'archive'],['Remove row','remove']];
  if(r.permissionState!=='grant-recorded')actions.push(['Correct mistaken ending','correct-ending']);
  $('detail-actions').replaceChildren(...actions.map(([label,action])=>button(label,()=>{$('detail-dialog').close();openForm(action,r);},action==='remove'?'danger-quiet':'secondary')));
  $('detail-dialog').showModal();
}
function field(parent,id,label,value,type='text',options=null,required=false,wide=false,hint=''){
  const wrapper=el('label',undefined,'field'+(wide?' wide':''));wrapper.append(el('span',label));
  let input;
  if(options){input=el('select');for(const [v,t] of options){const opt=el('option',t);opt.value=v;input.append(opt);}}
  else if(type==='textarea'){input=el('textarea');}
  else {input=el('input');input.type=type;if(type==='datetime-local')input.step='1';}
  input.id='field-'+id;input.name=id;input.required=required;
  input.value=value===null||value===undefined?'':String(value);
  wrapper.append(input);if(hint)wrapper.append(el('span',hint,'hint'));parent.append(wrapper);return input;
}
function rawRow(record){return Object.fromEntries(baseFields.map(k=>[k,record[k]]));}
function freshRow(source=null){return {licenseId:state.nextId,gameName:source?.gameName||'',universeId:source?.universeId||'',groupId:source?.groupId||'',grantor:source?.grantor||'RanuRbx',basis:'owner-issued-permission',agreementId:null,operatorAcceptanceRecorded:false,startsAt:state.now,expiresAt:null,duration:'fixed-term',revocableAtWill:null,registryRemovalTerminatesPermission:false,registryStatus:'listed',grantReference:null,scopeReference:null,terminationTermsReference:null};}
const titles={create:'Add a game permission',edit:'Record an amendment or correction',extend:'Extend a recorded term',end:'Record a completed ending',regrant:'Issue a separate new grant',archive:'Archive listing(s)',unarchive:'Unarchive listing(s)',remove:'Remove public row(s)',recover:'Recover a removed row', 'correct-ending':'Correct a mistaken ending',initialize:'Initialize / save registry format',mirror:'Export the private mirror'};
const descriptions={create:'Record an actual issued grant. Public references should identify documents without revealing private evidence.',edit:'Use the effective amendment or factual correction. This form does not create new revocation rights by itself.',extend:'Record an issued extension to an unexpired fixed term. After expiry, use “Give permission again.”',end:'Record an ending that has already taken effect under an applicable procedure. This does not send notice.',regrant:'Creates a new license ID for the same game. The old record and any gap remain intact.',archive:'Archives the listing only. Permission is unchanged.',unarchive:'Makes the listing visible as listed. Permission is unchanged.',remove:'Deletes the public row. This does not revoke permission. The row remains recoverable from private history.',recover:'Recovers the recorded row as archived. This does not grant permission again.', 'correct-ending':'Only for an ending assertion that was factually mistaken. To grant permission again, create a new grant.',initialize:'Saves an empty registry or its supported format. Existing grant terms are preserved.',mirror:'Copies the saved canonical registry to the configured private mirror. The existing mirror is backed up first.'};
function openForm(action,record=null,ids=null){
  if(!state)return;formContext={action,record,ids,revision:state.revision};
  $('form-title').textContent=titles[action];$('form-description').textContent=descriptions[action];$('form-error').textContent='';$('form-fields').replaceChildren();$('evidence-fields').replaceChildren();
  const fields=$('form-fields');
  if(['create','edit','regrant'].includes(action)){
    const row=action==='edit'?rawRow(record):freshRow(action==='regrant'?record:null);
    field(fields,'licenseId','License ID',row.licenseId,'text',null,true).disabled=action==='edit';
    field(fields,'gameName','Game name',row.gameName,'text',null,true);
    field(fields,'universeId','Roblox Universe ID',row.universeId,'text',null,true,false,'Experience ID, not an individual Place ID.');
    field(fields,'groupId','Roblox group ID',row.groupId,'text',null,true);
    field(fields,'grantor','Grantor',row.grantor,'text',null,true);
    field(fields,'basis','Permission basis',row.basis,'text',[['owner-issued-permission','Owner-issued permission'],['license-agreement','Actual license agreement']]);
    field(fields,'startsAt','Starts at · UTC',row.startsAt.slice(0,19),'datetime-local',null,true);
    const duration=field(fields,'duration','Duration',row.duration,'text',[['fixed-term','Fixed term'],['perpetual','No scheduled expiry']]);
    const expiry=field(fields,'expiresAt','Expires at · UTC',row.expiresAt?.slice(0,19)||'','datetime-local',null,row.duration==='fixed-term');
    duration.addEventListener('change',()=>{expiry.disabled=duration.value==='perpetual';expiry.required=!expiry.disabled;if(expiry.disabled)expiry.value='';});expiry.disabled=row.duration==='perpetual';
    field(fields,'revocableAtWill','At-will revocation terms',row.revocableAtWill===null?'unknown':String(row.revocableAtWill),'text',[['unknown','Unspecified'],['true','Expressly allowed by actual grant'],['false','Expressly prohibited by actual grant']]);
    for(const k of ['grantReference','scopeReference','terminationTermsReference','agreementId'])field(fields,k,labels[k],row[k],'text',null,action!=='edit'&&['grantReference','scopeReference'].includes(k));
    field(fields,'operatorAcceptanceRecorded','Actual operator acceptance recorded',String(row.operatorAcceptanceRecorded),'text',[['false','No acceptance recorded'],['true','Yes — evidence retained']]);
    field(fields,'registryStatus','Administrative listing',row.registryStatus,'text',[['listed','Listed'],['archived','Archived']]);
    if(action!=='edit')field(fields,'allowSameUniverse','Separate grant for an already listed universe',action==='regrant'?'true':'false','text',[['false','No'],['true','Yes, this is intentional']]);
  }else if(action==='extend')field(fields,'expiresAt','New expiry · UTC',record.expiresAt?.slice(0,19)||'','datetime-local',null,true);
  else if(action==='end'){
    field(fields,'mode','Ending basis','at-will','text',[['at-will','Express discretionary revocation'],['other-ground','Another established termination ground']]);
    field(fields,'effectiveAt','Actual effective time · UTC',state.now.slice(0,19),'datetime-local',null,true);
    field(fields,'statusReference','Public ending reference','','text',null,true,false,'An opaque, non-sensitive reference; detailed evidence stays private.');
    field(fields,'authorityReference','Private authority / terms reference','','text',null,true);
  }else if(ids||record){fields.append(el('p',(ids||[record.licenseId]).join(', '),'muted'));}
  const full=['create','edit','regrant','extend','end','correct-ending'].includes(action), ev=$('evidence-fields');
  if(full)field(ev,'reference','Evidence document/message reference','','text',null,true);
  if(full)field(ev,'deliveryEvidence','Delivery evidence, or why notice was not required','','text',null,true);
  field(ev,'explanation','What happened / reason for this record','','textarea',null,true,true);
  if(['create','edit','regrant'].includes(action))field(ev,'acceptanceEvidence','Acceptance evidence (required only if acceptance is recorded)','','text',null,false,true);
  $('form-dialog').showModal();
}
const value=id=>$('field-'+id)?.value||'';
function utcValue(id){const s=value(id);return s?s+(s.length===16?':00':'')+'Z':null;}
function payloadFromForm(){
  const {action,record,ids,revision}=formContext;
  const payload={action,revision,evidence:{explanation:value('explanation'),reference:value('reference'),deliveryEvidence:value('deliveryEvidence'),acceptanceEvidence:value('acceptanceEvidence')}};
  if(record)payload.licenseId=record.licenseId;
  if(['create','edit','regrant'].includes(action)){
    const row={};for(const k of baseFields)row[k]=value(k);
    for(const k of nullableFields)row[k]=value(k)||null;
    row.startsAt=utcValue('startsAt');row.expiresAt=value('duration')==='perpetual'?null:utcValue('expiresAt');
    row.revocableAtWill=value('revocableAtWill')==='unknown'?null:value('revocableAtWill')==='true';
    row.operatorAcceptanceRecorded=value('operatorAcceptanceRecorded')==='true';row.registryRemovalTerminatesPermission=false;
    payload.record=row;payload.allowSameUniverse=value('allowSameUniverse')==='true';
  }else if(action==='extend')payload.expiresAt=utcValue('expiresAt');
  else if(action==='end')Object.assign(payload,{mode:value('mode'),effectiveAt:utcValue('effectiveAt'),statusReference:value('statusReference'),authorityReference:value('authorityReference')});
  else if(['archive','unarchive','remove'].includes(action))payload.licenseIds=ids||[record.licenseId];
  return payload;
}
async function discard(){if(pendingPreview){try{await api('/api/discard',{previewId:pendingPreview.previewId});}catch(_){}pendingPreview=null;}$('preview-dialog').close();}
async function download(kind){try{const response=await fetch('/api/download/'+kind,{headers:{Authorization:'Bearer '+token}});if(!response.ok){const error=await response.json();throw new Error(error.error);}const blob=await response.blob(),url=URL.createObjectURL(blob),a=el('a');a.href=url;a.download='licenses.'+(kind==='csv'?'csv':'json');document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),5000);}catch(e){notice(e.message,true);}}

document.querySelectorAll('[data-close]').forEach(b=>b.addEventListener('click',()=>$(b.dataset.close).close()));
document.querySelectorAll('.nav').forEach(b=>b.addEventListener('click',()=>showView(b.dataset.view)));
$('refresh').addEventListener('click',()=>refresh(true));$('new-game').addEventListener('click',()=>openForm('create'));
$('search').addEventListener('input',renderRecords);$('filter').addEventListener('change',renderRecords);
$('select-all').addEventListener('change',()=>{visibleRecords().forEach(r=>$('select-all').checked?selection.add(r.licenseId):selection.delete(r.licenseId));renderRecords();});
for(const action of ['archive','unarchive','remove'])$('bulk-'+action).addEventListener('click',()=>openForm(action,null,[...selection]));
$('clear-selection').addEventListener('click',()=>{selection.clear();renderRecords();});
$('mirror').addEventListener('click',()=>openForm('mirror'));$('initialize').addEventListener('click',()=>openForm('initialize'));
$('download-json').addEventListener('click',()=>download('json'));$('download-csv').addEventListener('click',()=>download('csv'));
$('action-form').addEventListener('submit',async event=>{event.preventDefault();const b=event.submitter;b.disabled=true;$('form-error').textContent='';try{pendingPreview=await api('/api/preview',payloadFromForm());$('preview-target').textContent='Target: '+pendingPreview.target;$('preview-diff').textContent=pendingPreview.diff;$('preview-evidence').textContent=JSON.stringify(pendingPreview.evidence,null,2);$('preview-error').textContent='';$('preview-dialog').showModal();}catch(e){$('form-error').textContent=e.message;}finally{b.disabled=false;}});
$('back-preview').addEventListener('click',discard);$('discard-preview').addEventListener('click',discard);
$('preview-dialog').addEventListener('cancel',event=>{event.preventDefault();discard();});
$('save-preview').addEventListener('click',async()=>{if(!pendingPreview)return;const b=$('save-preview');b.disabled=true;try{const result=await api('/api/commit',{previewId:pendingPreview.previewId});pendingPreview=null;$('preview-dialog').close();$('form-dialog').close();selection.clear();await refresh();notice(result.message);}catch(e){$('preview-error').textContent=e.message;}finally{b.disabled=false;}});
refresh();
