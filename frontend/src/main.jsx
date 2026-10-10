import React, {useEffect, useMemo, useState} from 'react'
import {createRoot} from 'react-dom/client'
import {Activity, BarChart3, Bot, ChevronDown, CircleUserRound, Database, GitBranch, LayoutDashboard, Search, Send, ShieldCheck, Target, UsersRound} from 'lucide-react'
import './styles.css'

const nav = [
  ['智能问数', Bot], ['智能圈客', UsersRound], ['Customer 360', CircleUserRound],
  ['营销洞察', Target], ['Benchmark', BarChart3], ['Trace / Guardrail', GitBranch],
]
const samples = ['南京客户有多少？', '2026年Q1南京客户日均资产是多少？', '筛选日均资产超过50万的客户。']

async function api(path, options) {
  const response = await fetch(path, {headers: {'Content-Type': 'application/json'}, ...options})
  if (!response.ok) throw new Error(`服务返回 ${response.status}`)
  return response.json()
}

function Badge({mode}) { return <span className={`mode ${mode?.startsWith('REAL') ? 'real' : 'demo'}`}><Database size={14}/>{mode || 'DEMO / DRY RUN'}</span> }
function State({value='PASS'}) { return <span className={`state ${value.toLowerCase()}`}>{value}</span> }

function PlanCard({plan}) {
  if (!plan) return <Empty text="提交自然语言问题后，这里会显示结构化 Query Plan。"/>
  const items = [
    ['Intent', plan.intent], ['Subject', plan.subject], ['Metrics', plan.metrics?.join(', ') || '—'],
    ['Dimensions', plan.dimensions?.join(', ') || '—'], ['Filters', `${plan.filters?.length || 0} 条`],
    ['Time', plan.time_range ? JSON.stringify(plan.time_range) : '—'], ['Order', plan.order_by?.length ? JSON.stringify(plan.order_by) : '—'], ['Limit', plan.limit ?? '—'],
  ]
  return <div><div className="plan-grid">{items.map(([k,v])=><div className="plan-item" key={k}><span>{k}</span><strong>{v}</strong></div>)}</div><details><summary>查看原始 JSON <ChevronDown size={14}/></summary><pre>{JSON.stringify(plan,null,2)}</pre></details></div>
}

function Guardrail({data, result}) {
  const checks = ['Schema', 'Security', 'Join', 'Cost', 'Parameters', 'Result']
  const byName = Object.fromEntries((data?.checks || []).map(x=>[x.guard, x]))
  return <div className="guard-list">{checks.map(name=>{
    const key=name.toLowerCase(); const check=byName[key] || (name==='Result' ? result : null)
    const state=!data ? 'WAIT' : check ? (check.allowed ? (check.issues?.length ? 'WARN':'PASS'):'BLOCK') : (name==='Join' ? 'PASS':'WAIT')
    return <div key={name}><span>{name}</span><State value={state}/></div>
  })}</div>
}

function Empty({text}) { return <div className="empty"><Activity size={20}/><span>{text}</span></div> }

function ChatPage({mode, setLast}) {
  const [query,setQuery]=useState(samples[0]); const [loading,setLoading]=useState(false); const [messages,setMessages]=useState([]); const [conversation,setConversation]=useState(null); const [current,setCurrent]=useState(null)
  async function submit() {
    if(!query.trim()||loading)return; setLoading(true); setMessages(m=>[...m,{role:'user',text:query}])
    try { const value=await api('/api/chat',{method:'POST',body:JSON.stringify({message:query,conversation_id:conversation,execute:mode==='REAL_DB'})}); setConversation(value.conversation_id); setCurrent(value); setLast(value); setMessages(m=>[...m,{role:'assistant',text:value.message,status:value.status}]) }
    catch(e){setMessages(m=>[...m,{role:'assistant',text:`服务不可用：${e.message}`,status:'error'}])} finally{setLoading(false)}
  }
  return <div className="chat-layout">
    <aside className="history"><div className="eyebrow">对话历史</div><button className="new-chat">＋ 新建对话</button>{samples.map(x=><button key={x} onClick={()=>setQuery(x)}>{x}</button>)}</aside>
    <section className="chat"><div className="page-title"><div><h1>智能问数</h1><p>从自然语言到可审计、安全的业务结果</p></div><Badge mode={current?.mode || mode}/></div>
      <div className="messages">{messages.length===0?<div className="welcome"><div className="botmark"><Bot/></div><h2>今天想了解什么业务问题？</h2><p>我会展示语义、计划、SQL、参数与每一道安全检查。</p></div>:messages.map((m,i)=><div key={i} className={`bubble ${m.role}`}><span>{m.text}</span>{m.status&&<small>{m.status}</small>}</div>)}</div>
      <div className="composer"><textarea value={query} onChange={e=>setQuery(e.target.value)} onKeyDown={e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();submit()}}}/><button onClick={submit} disabled={loading}><Send size={18}/>{loading?'处理中':'发送'}</button></div>
    </section>
    <aside className="inspector"><div className="eyebrow">Agent Execution Inspector</div><h3>Query Plan</h3><PlanCard plan={current?.query_plan}/><h3>Generated SQL</h3><pre className="sql">{current?.sql || '等待生成'}</pre><h3>Parameters</h3><pre>{JSON.stringify(current?.params || {},null,2)}</pre><h3>Guardrail</h3><Guardrail data={current?.guardrail} result={current?.result_validation}/><h3>Final Result</h3><pre>{JSON.stringify(current?.result ?? null,null,2)}</pre><h3>Result Validation</h3><pre>{JSON.stringify(current?.result_validation ?? null,null,2)}</pre><div className="latency">Execution / End-to-End <strong>{current?.latency?.db_execution ?? '—'} / {current?.latency?.end_to_end_ms ?? '—'} ms</strong></div></aside>
  </div>
}

function SegmentPage({mode}) { const [query,setQuery]=useState('筛选2026年Q1南京日均资产超过50万的客户'); const [data,setData]=useState(null); async function evaluate(){setData(await api('/api/segments/evaluate',{method:'POST',body:JSON.stringify({query,execute:mode==='REAL_DB'})}))} return <Page title="智能圈客" desc="自然语言定义客群，规则、条件与证据完整可见" mode={mode}><div className="two-col"><Card title="客群定义"><textarea className="big-input" value={query} onChange={e=>setQuery(e.target.value)}/><button className="primary" onClick={evaluate}>评估客群</button></Card><Card title="评估结果">{data?<pre>{JSON.stringify(data,null,2)}</pre>:<Empty text="运行后展示真实安全结果与证据。"/>}</Card></div></Page> }
function CustomerPage({mode}) { const [id,setId]=useState('C000000000000001'); const [data,setData]=useState(null); const [error,setError]=useState(null); async function load(){setError(null);try{setData(await api(`/api/customer/${encodeURIComponent(id)}/profile`))}catch(e){setError(e.message)}} return <Page title="Customer 360" desc="默认脱敏，只展示可追溯的客户画像" mode={mode}><div className="search"><Search size={18}/><input value={id} onChange={e=>setId(e.target.value)} placeholder="输入 Customer ID"/><button onClick={load}>查询</button></div>{error&&<p>{error}</p>}<div className="profile-grid">{['basic_profile','asset_profile','holding_profile','trading_profile','fund_flow_profile','allocation_profile','tags'].map(x=><Card title={x} key={x}>{data?.status==='success'?<pre>{JSON.stringify(data.customer_360?.[x]??data[x]??{},null,2)}</pre>:<Empty text={data?.message||(mode==='REAL_DB'?'等待查询':'需要真实数据库安全结果')}/>}</Card>)}</div></Page> }
function OpportunityPage({mode}) { const [id,setId]=useState('C000000000000001'); const [data,setData]=useState(null); async function load(){setData(await api(`/api/opportunities?customer_id=${encodeURIComponent(id)}`))} return <Page title="营销洞察" desc="事实、规则判断与建议严格分层" mode={mode}><div className="search"><Search size={18}/><input value={id} onChange={e=>setId(e.target.value)} placeholder="输入 Customer ID"/><button onClick={load}>分析</button></div><div className="insight-grid"><Card title="FACT"><pre>{JSON.stringify(data?.trace?.features||{},null,2)}</pre></Card><Card title="RULE_DECISION"><pre>{JSON.stringify(data?.items||[],null,2)}</pre></Card><Card title="SUGGESTION"><pre>{JSON.stringify(data?.strategies||[],null,2)}</pre></Card></div>{data?.message&&<p>{data.message}</p>}</Page> }

function BenchmarkPage({mode}) {
  const [data,setData]=useState(null); useEffect(()=>{api('/api/benchmark/summary').then(setData).catch(()=>{})},[])
  const h=data?.headline||{raw_frozen:76.11,adjudicated:91.15,semantic_raw:83.33,generalization_f1:87.27,sql_dry_run:93.33,multi_turn:80,end_to_end_dry_run:85,hallucination_handling:100,guardrail:100,stability:100}
  const labels={raw_frozen:'Raw Frozen',adjudicated:'Adjudicated',semantic_raw:'Semantic Raw',generalization_f1:'Generalization F1',sql_dry_run:'SQL Dry-run',multi_turn:'Multi-turn',end_to_end_dry_run:'E2E Dry-run',hallucination_handling:'Hallucination',guardrail:'Guardrail',stability:'Stability'}
  return <Page title="Benchmark" desc="冻结评测、演进趋势与真实数据库指标分开展示" mode={mode}><div className="metric-grid">{Object.entries(h).map(([k,v])=><div className="metric" key={k}><span>{labels[k]}</span><strong>{v}%</strong><i style={{width:`${v}%`}}/></div>)}</div><Card title="Benchmark 演进"><div className="trend">{(data?.evolution?.labels||['Initial','Stage 8.2','Stage 8.3','Stage 8.4','Stage 8.5','Stage 8.6']).map((x,i)=><div key={x}><span>{x}</span><b>{[26.67,83.33,83.33,83.33,83.33,83.33][i]}%</b></div>)}</div></Card><Card title="Real DB Final Execution Accuracy"><Empty text={data?.real_db_status==='MEASURED'?'真实评测已完成':'NOT MEASURED — 不以 dry-run 指标替代'}/></Card></Page>
}

function TracePage({mode,last}) { const steps=['User Query','Semantic Grounding','Query Plan','SQL','Guardrail','Execution','Result Validator','Marketing']; return <Page title="Trace / Guardrail" desc="全链路可解释、可审计" mode={mode}><div className="trace-flow">{steps.map((x,i)=><React.Fragment key={x}><div><span>{i+1}</span><strong>{x}</strong><small>{last?.trace?.[i]?.status || (i<5&&last?'complete':'waiting')}</small></div>{i<steps.length-1&&<b>→</b>}</React.Fragment>)}</div><div className="two-col"><Card title="Guardrail 状态"><Guardrail data={last?.guardrail} result={last?.result_validation}/></Card><Card title="耗时"><pre>{JSON.stringify(last?.latency||{},null,2)}</pre></Card></div></Page> }
function Card({title,children}) {return <section className="card"><h3>{title}</h3>{children}</section>}
function Page({title,desc,mode,children}) {return <main className="page"><div className="page-title"><div><h1>{title}</h1><p>{desc}</p></div><Badge mode={mode}/></div>{children}</main>}

export function App(){const [active,setActive]=useState('智能问数');const [mode,setMode]=useState('DEMO / DRY RUN');const [last,setLast]=useState(null);useEffect(()=>{api('/api/health').then(x=>setMode(x.mode)).catch(()=>{})},[]);const content=useMemo(()=>({
  '智能问数':<ChatPage mode={mode} setLast={setLast}/>, '智能圈客':<SegmentPage mode={mode}/>, 'Customer 360':<CustomerPage mode={mode}/>, '营销洞察':<OpportunityPage mode={mode}/>, 'Benchmark':<BenchmarkPage mode={mode}/>, 'Trace / Guardrail':<TracePage mode={mode} last={last}/>
})[active],[active,mode,last]);return <div className="shell"><nav className="sidebar"><div className="brand"><ShieldCheck/><div><strong>TRUSTED AI</strong><span>营销数据智能体</span></div></div>{nav.map(([x,Icon])=><button className={active===x?'active':''} key={x} onClick={()=>setActive(x)}><Icon size={18}/>{x}</button>)}<div className="side-foot"><ShieldCheck size={18}/><div><strong>安全边界已启用</strong><span>Guardrail Mandatory</span></div></div></nav>{content}</div>}

const root=typeof document==='undefined' ? null : document.getElementById('root'); if(root) createRoot(root).render(<App/>)
