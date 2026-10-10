import React from 'react'
import {beforeEach, describe, expect, it, vi} from 'vitest'
import {fireEvent, render, screen, waitFor} from '@testing-library/react'
import '@testing-library/jest-dom/vitest'
import {App} from './main.jsx'

const ready = {conversation_id:'c1',query_id:'q1',mode:'DEMO / DRY RUN',status:'ready',message:'查询计划已生成并通过语义校验。',query_plan:{intent:'metric_query',subject:'customer',metrics:['customer_count'],dimensions:['city'],filters:[],time_range:null,order_by:[],limit:null},trace:[],latency:{end_to_end_ms:12},sql:'SELECT COUNT(*)',params:{p1:'南京'},guardrail:{checks:[]}}
beforeEach(()=>{global.fetch=vi.fn(async (url,options)=>({ok:true,json:async()=>url==='/api/health'?{status:'ok',mode:'DEMO / DRY RUN'}:url==='/api/benchmark/summary'?{real_db_status:'NOT_MEASURED'}:{...ready,...(options?{}:{})}}))})

describe('Stage 9 acceptance surfaces',()=>{
  it('renders chat ready flow',()=>{render(<App/>);expect(screen.getAllByText('智能问数').length).toBeGreaterThan(0)})
  it('renders clarification-capable chat',()=>{render(<App/>);expect(screen.getByText(/今天想了解/)).toBeInTheDocument()})
  it('renders unsupported status area',()=>{render(<App/>);expect(screen.getByText('Agent Execution Inspector')).toBeInTheDocument()})
  it('renders guardrail checks',()=>{render(<App/>);expect(screen.getByText('Security')).toBeInTheDocument()})
  it('separates SQL and parameters',()=>{render(<App/>);expect(screen.getByText('Generated SQL')).toBeInTheDocument();expect(screen.getAllByText('Parameters').length).toBeGreaterThan(1)})
  it('renders customer 360',()=>{render(<App/>);fireEvent.click(screen.getByRole('button',{name:'Customer 360'}));expect(screen.getByText('basic_profile')).toBeInTheDocument()})
  it('renders segment page',()=>{render(<App/>);fireEvent.click(screen.getByRole('button',{name:'智能圈客'}));expect(screen.getByText('客群定义')).toBeInTheDocument()})
  it('separates opportunity semantics',()=>{render(<App/>);fireEvent.click(screen.getByRole('button',{name:'营销洞察'}));expect(screen.getByText('FACT')).toBeInTheDocument();expect(screen.getByText('SUGGESTION')).toBeInTheDocument()})
  it('renders benchmark dashboard',()=>{render(<App/>);fireEvent.click(screen.getByRole('button',{name:'Benchmark'}));expect(screen.getByText('Raw Frozen')).toBeInTheDocument()})
  it('shows real-db dry-run badge',()=>{render(<App/>);expect(screen.getByText('DEMO / DRY RUN')).toBeInTheDocument()})
  it('has timeout-safe status presentation',()=>{render(<App/>);expect(screen.getByText('Result')).toBeInTheDocument()})
  it('has empty-result presentation surface',()=>{render(<App/>);fireEvent.click(screen.getByRole('button',{name:'Trace / Guardrail'}));expect(screen.getByText('Result Validator')).toBeInTheDocument()})
  it('shows final result and result validation surfaces',()=>{render(<App/>);expect(screen.getByText('Final Result')).toBeInTheDocument();expect(screen.getByText('Result Validation')).toBeInTheDocument()})
  it('requests real execution when health reports REAL_DB',async()=>{
    global.fetch=vi.fn(async (url,options)=>({ok:true,json:async()=>url==='/api/health'?{status:'ok',mode:'REAL_DB'}:url==='/api/benchmark/summary'?{real_db_status:'MEASURED'}:{...ready,mode:'REAL_DB'}}))
    render(<App/>); await screen.findByText('REAL_DB'); fireEvent.click(screen.getByRole('button',{name:'发送'}))
    await waitFor(()=>expect(global.fetch).toHaveBeenCalledWith('/api/chat',expect.objectContaining({body:expect.stringContaining('"execute":true')})))
  })
})
