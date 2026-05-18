import { useState } from 'react'
import { EvidencePanel } from './EvidencePanel'
import { SystemStatusPanel } from './SystemStatusPanel'
import { DocumentsTable } from './DocumentsTable'
import { KnowledgeIngestPanel } from './KnowledgeIngestPanel'

export function RightPanelTabs(props: any) {
  const [tab, setTab] = useState<'evidence'|'system'|'docs'|'ingest'>('evidence')
  return <aside className='right'>
    <div className='mode'>
      <button className={tab==='evidence'?'pill on':'pill'} onClick={()=>setTab('evidence')}>证据</button>
      <button className={tab==='system'?'pill on':'pill'} onClick={()=>setTab('system')}>系统</button>
      <button className={tab==='docs'?'pill on':'pill'} onClick={()=>setTab('docs')}>文档</button>
      <button className={tab==='ingest'?'pill on':'pill'} onClick={()=>setTab('ingest')}>导入</button>
    </div>
    {tab==='evidence' && <EvidencePanel message={props.message} />}
    {tab==='system' && <SystemStatusPanel stats={props.stats} system={props.system} refreshing={false} onRefresh={props.onRefresh} />}
    {tab==='docs' && <DocumentsTable docs={props.docs} deletingId={null} onDelete={props.onDelete} />}
    {tab==='ingest' && <KnowledgeIngestPanel loading={false} onIngest={props.onIngest} result={null as any} onUpload={props.onUpload} />}
  </aside>
}
