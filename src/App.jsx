import React, { useEffect, useMemo, useState } from 'react';
import Login from './Login.jsx';
import { currentUser, clearToken, logout, changePassword, listUsers, createUser, setUserStatus, listAudit, listNodes, createNode, setNodeStatus, rotateNodeToken, listServers, createGameServer, controlServer, sendConsoleCommand, requestConsoleLogs, operateServerFiles, listServerTasks, getServerTask, minecraftAction, manageServerBackups, listBackupSchedules, createBackupSchedule, updateBackupSchedule, deleteBackupSchedule, manageServerMods, upgradeServerVersion, getServerAccess, listServerMembers, addServerMember, removeServerMember, getBillingSummary, startBillingCheckout, openBillingPortal, getOperationalMetrics } from './api.js';
import { motion, AnimatePresence } from 'framer-motion';
import { Activity, ArrowDownToLine, ArrowUpRight, Bell, Box, ChartNoAxesCombined, ChevronDown, CircleHelp, Command, Cpu, Database, FileText, Gamepad2, Gauge, HardDrive, LayoutDashboard, LifeBuoy, LogOut, Menu, MoreHorizontal, Network, Plus, Search, Server, Settings, ShieldCheck, Terminal, Users, Wallet, Wifi, X, Zap, Folder, FolderPlus, FilePlus, ChevronRight, RefreshCw, Save, Trash2, ArrowLeft, Send, LoaderCircle, FileCode, Download } from 'lucide-react';

const initialServers = [];
const nav = [
 {title:'NAVIGATION',items:[['Dashboard',LayoutDashboard],['Servers',Server],['Nodes',Network]]},
 {title:'FLEET & CONTROL',items:[['Users',Users],['Activity Logs',FileText],['Security',ShieldCheck]]},
 {title:'ACCOUNT',items:[['Billing',Wallet]]}
];
function Meter({value,color='purple'}) { return <div className="meter"><span className={color} style={{width:value+'%'}}/></div>; }
function Stat({icon:Icon,label,value,detail,trend}) { return <div className="stat-card"><div className="stat-top"><span className="stat-icon"><Icon size={17}/></span><span className="stat-trend">{trend}</span></div><div className="stat-value">{value}</div><div className="stat-label">{label}</div><div className="stat-detail">{detail}</div></div>; }
function DashboardApp({user,onLogout}){
 const [page,setPage]=useState('Dashboard'); const [collapsed,setCollapsed]=useState(false); const [searchOpen,setSearchOpen]=useState(false); const [notificationsOpen,setNotificationsOpen]=useState(false); const [searchValue,setSearchValue]=useState(''); const [servers,setServers]=useState(initialServers); const [nodes,setNodes]=useState([]); const [auditEvents,setAuditEvents]=useState([]); const [query,setQuery]=useState(''); const [sidebar,setSidebar]=useState(false); const [notice,setNotice]=useState('');
 useEffect(()=>{
  let alive=true;
  const load=async()=>{
   try{
    const [rows,nodeRows,auditRows]=await Promise.all([listServers(),user?.role==='admin'?listNodes():Promise.resolve([]),user?.role==='admin'?listAudit():Promise.resolve([])]);
    if(!alive)return;
    setNodes(nodeRows);
    setAuditEvents(auditRows);
    const byId=new Map(nodeRows.map(n=>[n.id,n]));
    setServers(rows.map(server=>{
     const node=byId.get(server.node_id);
     const memoryTotal=node?.memory_total||0;
     return {id:String(server.id),name:server.name,game:'Minecraft Java',node:node?.name||'Unknown node',
      status:server.status==='online'?'Online':server.status.charAt(0).toUpperCase()+server.status.slice(1),
      cpu:node?.cpu_percent||0,memoryMb:server.memory_mb,ram:memoryTotal?Math.min(100,Math.round(server.memory_mb*1048576/memoryTotal*100)):0,
      disk:0,players:'—',address:(node?.fqdn||'node')+':'+server.allocation_port,color:'cyan'};
    }));
   }catch(error){if(alive)setNotice(error.message);}
  };
  load();const timer=setInterval(load,12000);
  return()=>{alive=false;clearInterval(timer);};
 },[]);
 useEffect(()=>{const onKeyDown=(event)=>{if((event.metaKey||event.ctrlKey)&&event.key.toLowerCase()==='k'){event.preventDefault();setSearchOpen(true);}if(event.key==='Escape')setSearchOpen(false);};window.addEventListener('keydown',onKeyDown);return()=>window.removeEventListener('keydown',onKeyDown);},[]);
 const totalMemory=nodes.reduce((sum,n)=>sum+n.memory_total,0);
 const usedMemory=nodes.reduce((sum,n)=>sum+n.memory_used,0);
 const totalDisk=nodes.reduce((sum,n)=>sum+n.disk_total,0);
 const usedDisk=nodes.reduce((sum,n)=>sum+n.disk_used,0);
 const averageCpu=nodes.length?nodes.reduce((sum,n)=>sum+n.cpu_percent,0)/nodes.length:0;
 const memoryPercent=totalMemory?Math.min(100,Math.round(usedMemory/totalMemory*100)):0;
 const allocatedMemory=servers.reduce((sum,server)=>sum+(server.memoryMb||0)/1024,0);
 const diskPercent=totalDisk?Math.min(100,Math.round(usedDisk/totalDisk*100)):0;

 const filtered=useMemo(()=>servers.filter(s=>s.name.toLowerCase().includes(query.toLowerCase())),[servers,query]);
 const announce=(msg)=>{setNotice(msg);setTimeout(()=>setNotice(''),2600)};

 return <div className={'app-shell '+(collapsed?'shell-collapsed':'')}>
  <aside className={'sidebar '+(sidebar?'sidebar-open ':'')+(collapsed?'sidebar-collapsed':'')}><div className="brand"><div className="brand-mark"><Zap size={22} fill="currentColor"/></div><div className="brand-copy"><b>LPGP</b><small>MADE BY LIGHTINGPLAYS</small></div><button className="sidebar-collapse" onClick={()=>setCollapsed(v=>!v)} title={collapsed?'Expand sidebar':'Collapse sidebar'}><ChevronRight size={16}/></button><button className="mobile-close" onClick={()=>setSidebar(false)}><X size={18}/></button></div>
   <div className="workspace"><div className="workspace-avatar">L</div><div className="workspace-copy"><b>LPGP Network</b><small>{user?.role==='admin'?'Administrator workspace':'Customer workspace'}</small></div><ChevronDown size={15}/></div>\n   {user?.role==='admin'&&<button className="sidebar-deploy" onClick={()=>{setPage('Deploy Server');setSidebar(false)}}><Plus size={16}/><span>DEPLOY SERVER</span></button>}
   <nav>{nav.map(group=><div className="nav-group" key={group.title}><div className="nav-heading">{group.title}</div>{group.items.filter(([label])=>user?.role==='admin'||!['Users','Nodes','Activity Logs'].includes(label)).map(([label,Icon])=><button key={label} className={'nav-link '+(page===label?'active':'')} onClick={()=>{setPage(label);setSidebar(false)}}><Icon size={17}/><span>{label}</span>{label==='Servers'&&<i>{servers.length}</i>}</button>)}</div>)}</nav>
   <div className="sidebar-bottom"><div className="promo-card"><div className="promo-icon"><Zap size={17}/></div><b>Power your community</b><p>Your infrastructure, one beautiful control plane.</p><button onClick={()=>announce('Documentation will be connected in a later phase')}>Explore features <ArrowUpRight size={14}/></button></div><div className="profile"><div className="avatar">A</div><div className="profile-name"><b>{user?.username || 'Administrator'}</b><small>{user?.email || 'Admin account'}</small></div><MoreHorizontal size={18}/></div></div>
  </aside>
  {sidebar&&<div className="scrim" onClick={()=>setSidebar(false)}/>}
  <main className={'main '+(collapsed?'main-collapsed':'')}><header className="topbar"><div className="crumb"><button className="mobile-menu" onClick={()=>setSidebar(true)}><Menu size={19}/></button><span>Workspace</span><b>/</b><strong>{page}</strong></div><div className="top-actions"><button className="top-search" onClick={()=>{setSearchValue('');setSearchOpen(true)}}><Search size={15}/><span>Search anything</span><kbd>⌘ K</kbd></button><div className="status-pill"><span/>{nodes.length===0?'No nodes connected':nodes.every(n=>n.is_enabled&&n.last_heartbeat&&Date.now()-new Date(n.last_heartbeat).getTime()<60000)?'All nodes connected':'Node attention required'}</div>{user?.role==='admin'&&<button className="icon-button" aria-label="Open activity notifications" onClick={()=>setNotificationsOpen(v=>!v)}><Bell size={18}/>{auditEvents.length>0&&<i/>}</button>}<button className="help-button" onClick={onLogout}><LogOut size={16}/> <span>Sign out</span></button><button className="help-button" onClick={()=>announce('Help center coming soon')}><CircleHelp size={17}/> <span>Help</span></button></div></header>
  <AnimatePresence>{notificationsOpen&&<motion.div className="notification-popover" initial={{opacity:0,y:-6}} animate={{opacity:1,y:0}} exit={{opacity:0,y:-6}}><div className="notification-head"><div><b>Recent activity</b><small>Latest events recorded by LPGP</small></div><button onClick={()=>setNotificationsOpen(false)} aria-label="Close notifications"><X size={15}/></button></div>{auditEvents.slice(0,6).map(event=><div className="notification-item" key={event.id}><span><Activity size={14}/></span><div><b>{event.action}</b><small>{event.detail}</small><time>{new Date(event.created_at).toLocaleString()}</time></div></div>)}{auditEvents.length===0&&<div className="empty">No recent activity has been recorded.</div>}<button className="notification-view-all" onClick={()=>{setPage('Activity Logs');setNotificationsOpen(false)}}>Open activity log <ArrowUpRight size={14}/></button></motion.div>}</AnimatePresence>
  <div className="content"><div className="welcome-row"><div><div className="eyebrow"><span/> CONTROL CENTER <span className="eyebrow-line"/></div><h1>{page==='Dashboard'?'Welcome back, '+(user?.username||'Admin')+'.':page}</h1><p>{page==='Dashboard'?'Here’s what’s happening across your infrastructure today.':'Manage your LPGP infrastructure and services.'}</p></div><div className="welcome-actions"><button className="button-secondary" onClick={()=>announce('Activity report export is not connected yet')}><ArrowDownToLine size={16}/> Export report</button>{user?.role==='admin'&&<button className="button-primary" onClick={()=>setPage('Deploy Server')}><Plus size={17}/> Deploy server</button>}</div></div>
  {page==='Billing'?<BillingPage announce={announce}/>:page==='Security'?<SecurityPage announce={announce} user={user}/>:page==='Dashboard'?<>
   <div className="stats-grid"><Stat icon={Server} label="Total servers" value={String(servers.length).padStart(2,'0')} detail="Across all nodes" trend="↗ Live"/><Stat icon={Activity} label="Running servers" value={String(servers.filter(s=>s.status==='Online').length).padStart(2,'0')} detail="Ready to serve players" trend="● Healthy"/><Stat icon={Cpu} label="CPU utilization" value={averageCpu.toFixed(1)+"%"} detail={nodes.length+" reporting nodes"} trend="↗ Live"/><Stat icon={Database} label="Memory allocated" value={allocatedMemory.toFixed(1)+" GB"} detail={servers.length+" server allocations"} trend="↗ Live"/></div>
   <div className="section-heading"><div><h2>Infrastructure</h2><p>Real-time overview of your server fleet</p></div><button className="text-button" onClick={()=>setPage('Servers')}>View all servers <ArrowUpRight size={15}/></button></div>
   <div className="overview-grid"><div className="panel fleet-panel"><div className="panel-head"><div><h3>Server overview</h3><p>Your recently active instances</p></div><button className="dots" onClick={()=>announce('More server actions coming soon')}><MoreHorizontal size={19}/></button></div><div className="server-list">{servers.slice(0,3).map(s=><div className="server-row" key={s.id}><div className={'server-icon '+s.color}><Gamepad2 size={19}/></div><div className="server-info"><b>{s.name}</b><small>{s.game} · {s.node}</small></div><div className={'server-status '+(s.status==='Online'?'online':['Installing','Starting','Stopping','Deleting'].includes(s.status)?'installing':'offline')}><i/>{s.status}</div><div className="server-usage"><span>NODE CPU <b>{s.cpu.toFixed(1)}%</b></span><Meter value={s.cpu}/></div><button className="row-arrow" onClick={()=>{setPage('Servers')}}><ArrowUpRight size={17}/></button></div>)}</div><button className="view-servers" onClick={()=>setPage('Servers')}>Manage all servers <ArrowUpRight size={15}/></button></div>
    <div className="panel capacity-panel"><div className="panel-head"><div><h3>Node capacity</h3><p>Combined resource allocation</p></div><span className="live-tag"><i/> LIVE</span></div><div className="capacity-total"><div><strong>{(totalMemory/1024**3).toFixed(1)} <small>GB</small></strong><span>Total memory</span></div><div className="capacity-ring" style={{background:"conic-gradient(#45b8f2 0 "+memoryPercent+"%,#20364a "+memoryPercent+"% 100%)"}}><div><b>{memoryPercent}%</b><small>USED</small></div></div></div><div className="capacity-bars"><div><div><span><i className="legend purple-bg"/>Memory</span><b>{(usedMemory/1024**3).toFixed(1)} / {(totalMemory/1024**3).toFixed(1)} GB</b></div><Meter value={memoryPercent}/></div><div><div><span><i className="legend cyan-bg"/>Storage</span><b>{(usedDisk/1024**3).toFixed(1)} / {(totalDisk/1024**3).toFixed(1)} GB</b></div><Meter value={diskPercent} color="cyan"/></div><div><div><span><i className="legend orange-bg"/>CPU</span><b>{averageCpu.toFixed(1)}% average</b></div><Meter value={averageCpu} color="orange"/></div></div></div></div>
   <div className="bottom-grid"><div className="panel activity-panel"><div className="panel-head"><div><h3>Recent activity</h3><p>Latest events from your panel</p></div><button className="text-button" onClick={()=>setPage('Activity Logs')}>View logs <ArrowUpRight size={14}/></button></div>{auditEvents.slice(0,4).map(event=><div className="activity-item" key={event.id}><span className="activity-dot purple-dot"><Activity size={14}/></span><div><b>{event.action}</b><small>{event.detail}</small></div><time>{new Date(event.created_at).toLocaleString()}</time></div>)}{auditEvents.length===0&&<div className="empty">No recorded activity yet.</div>}</div><div className="panel quick-panel"><div className="panel-head"><div><h3>Quick actions</h3><p>Jump into your workflow</p></div></div><div className="quick-grid"><button onClick={()=>setPage('Deploy Server')}><span><Plus size={18}/></span><b>Deploy server</b><small>Deploy an instance</small></button>{user?.role==='admin'&&<button onClick={()=>setPage('Nodes')}><span><Network size={18}/></span><b>Add node</b><small>Expand infrastructure</small></button>}{user?.role==='admin'&&<button onClick={()=>setPage('Users')}><span><Users size={18}/></span><b>Invite user</b><small>Manage your team</small></button>}{user?.role==='admin'&&<button onClick={()=>setPage('Activity Logs')}><span><Terminal size={18}/></span><b>View logs</b><small>Inspect system events</small></button>}</div></div></div>
  </>:page==='Servers'?<RealServersPage announce={announce} user={user} initialQuery={query}/>:page==='Deploy Server'?<RealServersPage announce={announce} user={user} initialOpen/>:page==='Users'?<UsersPage announce={announce}/>:page==='Nodes'?<NodesPage announce={announce}/>:page==='Activity Logs'?<ActivityLogsPage/>:<div className="panel placeholder-page"><div className="placeholder-icon"><Command size={28}/></div><h2>{page}</h2><p>This module is part of the LPGP roadmap. The dashboard and server-list demo are ready to explore.</p><button className="button-primary" onClick={()=>setPage('Dashboard')}>Back to dashboard</button></div>}
  <footer><span>© 2026 LPGP</span><span><i/> {nodes.length===0?'No nodes connected':nodes.every(n=>n.is_enabled&&n.last_heartbeat&&Date.now()-new Date(n.last_heartbeat).getTime()<60000)?'All nodes connected':'Node attention required'}</span><span>Built for your infrastructure <Zap size={12}/></span></footer></div></main>
  <AnimatePresence>{searchOpen&&<motion.div className="command-backdrop" initial={{opacity:0}} animate={{opacity:1}} exit={{opacity:0}} onMouseDown={e=>{if(e.target===e.currentTarget)setSearchOpen(false)}}><motion.div className="command-palette" initial={{y:12,opacity:0,scale:.98}} animate={{y:0,opacity:1,scale:1}} exit={{y:12,opacity:0,scale:.98}}><div className="command-input-row"><Search size={18}/><input autoFocus value={searchValue} onChange={e=>setSearchValue(e.target.value)} placeholder="Search pages and servers…" onKeyDown={e=>{if(e.key==='Enter'){const match=servers.find(server=>server.name.toLowerCase().includes(searchValue.toLowerCase()));if(match){setQuery(match.name);setPage('Servers');setSearchOpen(false);}else{const pageMatch=['Dashboard','Servers','Nodes','Users','Activity Logs','Security','Billing'].find(label=>label.toLowerCase().includes(searchValue.toLowerCase()));if(pageMatch){setQuery('');setPage(pageMatch);setSearchOpen(false);}}}}}/><kbd>ESC</kbd><button onClick={()=>setSearchOpen(false)} aria-label="Close search"><X size={17}/></button></div><div className="command-results"><small>PAGES</small>{['Dashboard','Servers','Nodes','Users','Activity Logs','Security','Billing'].filter(label=>label.toLowerCase().includes(searchValue.toLowerCase())).map(label=><button key={label} onClick={()=>{setQuery('');setPage(label);setSearchOpen(false)}}><span className="command-result-icon"><LayoutDashboard size={15}/></span><span>{label}</span><ArrowUpRight size={14}/></button>)}<small>SERVERS</small>{servers.filter(server=>server.name.toLowerCase().includes(searchValue.toLowerCase())).slice(0,6).map(server=><button key={server.id} onClick={()=>{setQuery(server.name);setPage('Servers');setSearchOpen(false)}}><span className="command-result-icon"><Gamepad2 size={15}/></span><span>{server.name}<em>{server.status} · Minecraft Java</em></span><ArrowUpRight size={14}/></button>)}{searchValue&&['Dashboard','Servers','Nodes','Users','Activity Logs','Security','Billing'].every(label=>!label.toLowerCase().includes(searchValue.toLowerCase()))&&!servers.some(server=>server.name.toLowerCase().includes(searchValue.toLowerCase()))&&<div className="command-no-results">No matching pages or servers.</div>}</div><div className="command-footer"><span>Navigate LPGP</span><span><kbd>↵</kbd> Open <kbd>ESC</kbd> Close</span></div></motion.div></motion.div>}</AnimatePresence>
  <AnimatePresence>{notice&&<motion.div className="toast" initial={{opacity:0,y:12}} animate={{opacity:1,y:0}} exit={{opacity:0,y:12}}><ShieldCheck size={17}/>{notice}</motion.div>}</AnimatePresence>
 </div>
}



function BillingPage({announce}){
 const [data,setData]=useState(null),[busy,setBusy]=useState(false),[error,setError]=useState('');
 async function load(){try{setError('');setData(await getBillingSummary());}catch(e){setError(e.message);}}
 useEffect(()=>{load();},[]);
 async function checkout(){setBusy(true);setError('');try{const result=await startBillingCheckout();window.location.assign(result.checkout_url);}catch(e){setError(e.message);setBusy(false);}}
 async function portal(){setBusy(true);setError('');try{const result=await openBillingPortal();window.location.assign(result.portal_url);}catch(e){setError(e.message);setBusy(false);}}
 const subscription=data?.subscription||{};
 const money=(amount,currency)=>new Intl.NumberFormat(undefined,{style:'currency',currency:(currency||'usd').toUpperCase()}).format((amount||0)/100);
 return <div className="billing-page"><div className="panel billing-plan"><div className="billing-plan-icon"><Wallet size={22}/></div><div className="billing-plan-copy"><span className="eyebrow">ACCOUNT BILLING</span><h2>Subscription & payments</h2><p>Secure recurring payments powered by Stripe Checkout. Your card details are handled by Stripe, not stored by LPGP.</p></div><span className={'billing-status '+(subscription.status==='active'?'active':'')}>{subscription.status||'Loading'}</span><div className="billing-plan-actions">{subscription.status==='active'||subscription.status==='trialing'||subscription.status==='past_due'?<button className="button-primary" disabled={busy} onClick={portal}>Manage subscription <ArrowUpRight size={15}/></button>:<button className="button-primary" disabled={busy||!data} onClick={checkout}>{busy?'Opening secure checkout…':'Choose subscription plan'} <ArrowUpRight size={15}/></button>}<button className="button-secondary" disabled={busy} onClick={load}><RefreshCw size={15}/> Refresh</button></div>{subscription.current_period_end&&<small className="billing-renewal">Current period ends {new Date(subscription.current_period_end).toLocaleString()}</small>}</div>{error&&<div className="auth-error">{error}</div>}<div className="panel billing-invoices"><div className="panel-head"><div><h3>Payment history</h3><p>Invoices and payment status from Stripe</p></div><span className="live-tag"><i/> SECURE</span></div>{!data?<div className="empty">Loading billing information…</div>:data.invoices.length===0?<div className="empty">No invoices yet. Your payment history will appear here after your first successful billing event.</div>:data.invoices.map(invoice=><div className="billing-invoice" key={invoice.id}><div className="billing-invoice-icon"><FileText size={17}/></div><div className="billing-invoice-info"><b>Invoice #{invoice.id}</b><small>{new Date(invoice.created_at).toLocaleDateString()} · {invoice.status}</small></div><strong>{money(invoice.amount_paid||invoice.amount_due,invoice.currency)}</strong>{invoice.hosted_invoice_url&&<a href={invoice.hosted_invoice_url} target="_blank" rel="noreferrer">View invoice <ArrowUpRight size={13}/></a>}</div>)}</div><div className="billing-note"><ShieldCheck size={16}/> Billing activates only after Stripe confirms the subscription through a verified webhook. Configure your Stripe Price ID and webhook secret in the API environment.</div></div>
}

function SecurityPage({announce,user}){
 const [metrics,setMetrics]=useState(null),[error,setError]=useState('');
 const [currentPassword,setCurrentPassword]=useState(''),[newPassword,setNewPassword]=useState(''),[confirmPassword,setConfirmPassword]=useState('');
 const [saving,setSaving]=useState(false),[passwordMessage,setPasswordMessage]=useState('');
 useEffect(()=>{if(user?.role!=='admin')return;let alive=true;const load=()=>getOperationalMetrics().then(v=>{if(alive){setMetrics(v);setError('');}}).catch(e=>{if(alive)setError(e.message);});load();const timer=setInterval(load,15000);return()=>{alive=false;clearInterval(timer);};},[user?.role]);
 async function submitPassword(e){
  e.preventDefault();setPasswordMessage('');setError('');
  if(newPassword!==confirmPassword){setError('New password and confirmation do not match.');return;}
  setSaving(true);
  try{const result=await changePassword({current_password:currentPassword,new_password:newPassword});setPasswordMessage(result.message||'Password changed successfully.');setCurrentPassword('');setNewPassword('');setConfirmPassword('');announce('Account password updated');}
  catch(e){setError(e.message);}
  finally{setSaving(false);}
 }
 const tiles=metrics?[['Servers',metrics.servers.total+' total',metrics.servers.online+' online · '+metrics.servers.error+' errors'],['Nodes',metrics.nodes.total+' total',metrics.nodes.online+' online · '+metrics.nodes.offline+' offline'],['Task queue',metrics.tasks.pending+' pending',metrics.tasks.claimed+' claimed · '+metrics.tasks.failed+' failed'],['Customers',String(metrics.users.active),'Active accounts']]:[];
 return <div className="ops-grid">
  <div className="panel security-account-card">
   <div className="panel-head"><div><h3>Account security</h3><p>Change the password used to sign in to LPGP.</p></div><span className="live-tag"><i/> AUTHENTICATED</span></div>
   <form className="user-create-form" onSubmit={submitPassword}>
    <div className="user-form-grid">
     <input type="password" autoComplete="current-password" placeholder="Current password" value={currentPassword} onChange={e=>setCurrentPassword(e.target.value)} required/>
     <input type="password" autoComplete="new-password" placeholder="New password (12+ characters)" minLength="12" maxLength="128" value={newPassword} onChange={e=>setNewPassword(e.target.value)} required/>
     <input type="password" autoComplete="new-password" placeholder="Confirm new password" minLength="12" maxLength="128" value={confirmPassword} onChange={e=>setConfirmPassword(e.target.value)} required/>
    </div>
    <small className="muted">Your current password is verified by the API. Passwords are stored as Argon2 hashes; the panel never displays or retrieves an existing password.</small>
    <button className="button-primary" disabled={saving||!currentPassword||newPassword.length<12||!confirmPassword}>{saving?'Updating password…':'Update password'}</button>
    {passwordMessage&&<p className="billing-renewal">{passwordMessage}</p>}
   </form>
  </div>
  {user?.role==='admin'&&<>
   {error&&<div className="auth-error">{error}</div>}
   <div className="section-heading"><div><h2>Platform operations</h2><p>Live infrastructure counters, refreshed every 15 seconds</p></div></div>
   <div className="stats-grid">{tiles.map(([label,value,detail])=><div className="stat-card" key={label}><div className="stat-label">{label}</div><div className="stat-value">{value}</div><div className="stat-detail">{detail}</div></div>)}</div>
   <div className="panel ops-status"><div className="panel-head"><div><h3>Production health</h3><p>Operational endpoints exposed by the LPGP API</p></div><span className="live-tag"><i/> AUTO REFRESH 15S</span></div><div className="ops-endpoints"><span><i/> Liveness endpoint <code>/health/live</code></span><span><i/> Database readiness <code>/health/ready</code></span><span><i/> Admin metrics <code>/admin/metrics</code></span></div>{metrics&&<small className="billing-renewal">Updated {new Date(metrics.generated_at).toLocaleString()}</small>}</div>
  </>}
 </div>;
}

function RealServersPage({announce,user,initialOpen=false,initialQuery=''}){
 const [servers,setServers]=useState([]),[nodes,setNodes]=useState([]),[loading,setLoading]=useState(true),[error,setError]=useState(''),[saving,setSaving]=useState(false),[query,setQuery]=useState(initialQuery),[show,setShow]=useState(initialOpen);
 const [form,setForm]=useState({name:'',node_id:'',owner_email:'',version:'LATEST',server_type:'paper',memory_mb:2048,cpu_limit:2});
 const [selectedServer,setSelectedServer]=useState(null);
 async function refresh(){
  try{const [serverRows,nodeRows]=await Promise.all([listServers(),user?.role==='admin'?listNodes():Promise.resolve([])]);setServers(serverRows);setNodes(nodeRows);setError('');}
  catch(e){setError(e.message);}
  finally{setLoading(false);}
 }
 useEffect(()=>{refresh();const timer=setInterval(refresh,8000);return()=>clearInterval(timer);},[]);
 const filtered=servers.filter(s=>s.name.toLowerCase().includes(query.toLowerCase()));
 async function submit(e){
  e.preventDefault();setSaving(true);setError('');
  try{await createGameServer({...form,node_id:Number(form.node_id),memory_mb:Number(form.memory_mb),cpu_limit:Number(form.cpu_limit)});setShow(false);setForm({name:'',node_id:'',owner_email:'',version:'LATEST',server_type:'paper',memory_mb:2048,cpu_limit:2});await refresh();announce('Server provisioning queued on VPS node');}
  catch(e){setError(e.message);}
  finally{setSaving(false);}
 }
 async function action(server,verb){
  if(verb==='delete'&&!window.confirm('Delete '+server.name+' and its persistent world data? This cannot be undone.'))return;
  try{await controlServer(server.id,verb);await refresh();announce(verb[0].toUpperCase()+verb.slice(1)+' queued for '+server.name);}
  catch(e){setError(e.message);}
 }
 const nodeById=id=>nodes.find(n=>n.id===id);
 const online=n=>n?.last_heartbeat&&Date.now()-new Date(n.last_heartbeat).getTime()<60000;
 const statusLabel=s=>({installing:'Installing',starting:'Starting',stopping:'Stopping',deleting:'Deleting',online:'Running',offline:'Offline',error:'Error'}[s]||s);
 return <div className="panel servers-page">
  <div className="panel-head"><div><h3>Minecraft servers</h3><p>Your servers and any instances shared with your account</p></div>{user?.role==='admin'&&<button className="button-primary" onClick={()=>setShow(v=>!v)}><Plus size={16}/> Deploy server</button>}</div>
  {error&&<div className="auth-error">{error}</div>}
  {show&&user?.role==='admin'&&<form className="user-create-form" onSubmit={submit}><h3>Deploy Minecraft Java server</h3><div className="user-form-grid">
   <input placeholder="Server name" minLength="3" maxLength="48" value={form.name} onChange={e=>setForm({...form,name:e.target.value})} required/>
   <input type="email" placeholder="Customer email (optional — assign ownership)" value={form.owner_email} onChange={e=>setForm({...form,owner_email:e.target.value})}/>
   <select value={form.node_id} onChange={e=>setForm({...form,node_id:e.target.value})} required><option value="">Choose online node</option>{nodes.filter(n=>n.is_enabled&&online(n)).map(n=><option key={n.id} value={n.id}>{n.name} · {n.fqdn}</option>)}</select>
   <select value={form.server_type} onChange={e=>setForm({...form,server_type:e.target.value})}><option value='paper'>Paper</option><option value='fabric'>Fabric</option><option value='forge'>Forge</option></select>
   <select value={form.version} onChange={e=>setForm({...form,version:e.target.value})}><option value="LATEST">Latest Minecraft</option><option value="1.21.4">1.21.4</option><option value="1.21.1">1.21.1</option><option value="1.20.4">1.20.4</option></select>
   <select value={form.memory_mb} onChange={e=>setForm({...form,memory_mb:Number(e.target.value)})}><option value={1024}>1 GB RAM</option><option value={2048}>2 GB RAM</option><option value={4096}>4 GB RAM</option><option value={6144}>6 GB RAM</option><option value={8192}>8 GB RAM</option></select>
   <select value={form.cpu_limit} onChange={e=>setForm({...form,cpu_limit:Number(e.target.value)})}><option value={1}>1 vCPU</option><option value={2}>2 vCPU</option><option value={3}>3 vCPU</option><option value={4}>4 vCPU</option></select>
  </div><p className="muted">Creates a persistent Docker container with a dedicated TCP allocation. The node must be online and have enough free RAM.</p><button className="button-primary" disabled={saving||nodes.filter(n=>n.is_enabled&&online(n)).length===0}>{saving?'Queueing deployment…':'Deploy Minecraft server'}</button></form>}
  <div className="toolbar"><div className="search-box"><Search size={16}/><input placeholder="Search your servers…" value={query} onChange={e=>setQuery(e.target.value)}/></div><span className="muted">{servers.length} deployed</span></div>
  <div className="fleet-summary-grid">
   <div className="fleet-summary"><span>TOTAL SERVERS</span><b>{servers.length.toString().padStart(2,'0')}</b><small>Instances in your account</small></div>
   <div className="fleet-summary"><span>ONLINE</span><b>{servers.filter(s=>s.status==='online').length.toString().padStart(2,'0')}</b><small>Running game servers</small></div>
   <div className="fleet-summary"><span>PROVISIONING</span><b>{servers.filter(s=>['installing','starting','stopping'].includes(s.status)).length.toString().padStart(2,'0')}</b><small>Pending node tasks</small></div>
  </div>
  {loading?<p className="muted">Loading server inventory from API…</p>:<div className="fleet-server-grid">{filtered.map(server=>{const node=nodeById(server.node_id);const busy=['installing','starting','stopping','deleting'].includes(server.status);return <article className="fleet-server-card" key={server.id}>
   <div className="fleet-server-card-top"><div className="fleet-server-symbol"><Gamepad2 size={21}/></div><span className={'server-status '+(server.status==='online'?'online':['installing','starting','stopping','deleting'].includes(server.status)?'installing':'offline')}><i/>{statusLabel(server.status)}</span></div>
   <h3>{server.name}</h3><p className="fleet-server-version">Minecraft Java <span>·</span> {server.version}</p>
   <div className="fleet-server-details"><div><small>NODE</small><b>{node?.name||'Unknown node'}</b></div><div><small>MEMORY</small><b>{server.memory_mb} MB</b></div><div><small>CPU</small><b>{server.cpu_limit} vCPU</b></div><div><small>ALLOCATION</small><b>{node?.fqdn||'node'}:{server.allocation_port}</b></div></div>
   {server.last_error&&<div className="server-error">{server.last_error}</div>}
   <div className="fleet-server-actions"><button className="button-primary" onClick={()=>setSelectedServer(server)}>Manage server <ArrowUpRight size={14}/></button><button className="small-action" disabled={busy||server.status==='error'} onClick={()=>action(server,server.status==='online'?'stop':'start')}>{server.status==='online'?'Stop':'Start'}</button><button className="small-action ghost" disabled={busy||server.status==='error'} onClick={()=>action(server,'restart')} title="Restart server"><RefreshCw size={13}/></button><button className="small-action danger" disabled={busy} onClick={()=>action(server,'delete')} title="Delete server"><Trash2 size={13}/></button></div>
  </article>})}{filtered.length===0&&<div className="empty fleet-empty">{servers.length?'No servers match your search.':'No servers deployed yet. Enroll an online VPS node, then deploy your first Minecraft server.'}</div>}</div>}
  {selectedServer&&<ServerWorkspace server={selectedServer} onClose={()=>setSelectedServer(null)} announce={announce} user={user}/>}
 </div>;
}


function ServerWorkspace({server,onClose,announce,user}){
 const [tab,setTab]=useState('overview'),[tasks,setTasks]=useState([]),[logs,setLogs]=useState('Waiting for node console output…'),[command,setCommand]=useState(''),[busy,setBusy]=useState(false),[error,setError]=useState('');
 const [path,setPath]=useState('.'),[entries,setEntries]=useState([]),[filePath,setFilePath]=useState(''),[fileText,setFileText]=useState('');
 const [mods,setMods]=useState([]),[modKind,setModKind]=useState('plugin'),[modUrl,setModUrl]=useState(''),[modFilename,setModFilename]=useState(''),[backups,setBackups]=useState([]),[backupSchedules,setBackupSchedules]=useState([]),[scheduleForm,setScheduleForm]=useState({name:'Daily backup',frequency:'daily',retention:7,enabled:true}),[versionChoice,setVersionChoice]=useState(server.version==='LATEST'?'1.21.11':server.version);
 const [player,setPlayer]=useState(''),[difficulty,setDifficulty]=useState('normal'),[gameMode,setGameMode]=useState('survival'),[worldTime,setWorldTime]=useState('day'),[weather,setWeather]=useState('clear');
 const [serverSettings,setServerSettings]=useState({motd:'A Minecraft Server','max-players':'20',difficulty:'easy',gamemode:'survival',pvp:'true','white-list':'false','spawn-protection':'16','view-distance':'10','simulation-distance':'10'}),[settingsLoaded,setSettingsLoaded]=useState(false);
 const [access,setAccess]=useState({is_owner:false,permissions:[]}),[members,setMembers]=useState([]),[memberEmail,setMemberEmail]=useState(''),[memberPermissions,setMemberPermissions]=useState(['server.read']),[membersLoading,setMembersLoading]=useState(false);
 useEffect(()=>{getServerAccess(server.id).then(result=>{setAccess(result);const p=result.permissions||[];if(!p.includes('control.console'))setTab(p.includes('server.read')?'overview':p.includes('file.read')||p.includes('file.write')?'files':p.some(x=>x.startsWith('backup.'))?'backups':p.includes('server.manage')?'minecraft':'none');}).catch(e=>setError(e.message));},[server.id]);
 async function refreshMembers(){setMembersLoading(true);try{setMembers(await listServerMembers(server.id));}catch(e){setError(e.message);}finally{setMembersLoading(false);}}
 async function inviteMember(e){e.preventDefault();setBusy(true);setError('');try{await addServerMember(server.id,{email:memberEmail,permissions:memberPermissions});setMemberEmail('');await refreshMembers();announce('Team member access granted');}catch(e){setError(e.message);}finally{setBusy(false);}}
 async function revokeMember(id){if(!window.confirm('Revoke this member access to this server?'))return;try{await removeServerMember(server.id,id);await refreshMembers();announce('Team member access revoked');}catch(e){setError(e.message);}}
 const can=(permission)=>access.permissions.includes(permission);
 async function refreshTasks(){
  const rows=await listServerTasks(server.id);setTasks(rows);
  const latest=rows.filter(t=>t.action==='console_logs'&&t.status==='completed').at(-1);
  if(latest?.result?.data?.output)setLogs(latest.result.data.output);
 }
 useEffect(()=>{
  let alive=true;
  const tick=async()=>{try{if(tab==='console')await requestConsoleLogs(server.id);const rows=await listServerTasks(server.id);if(!alive)return;setTasks(rows);const latest=rows.filter(t=>t.action==='console_logs'&&t.status==='completed').at(-1);if(latest?.result?.data?.output)setLogs(latest.result.data.output);}catch(e){if(alive)setError(e.message);}};
  tick();const timer=setInterval(tick,3000);return()=>{alive=false;clearInterval(timer);};
 },[server.id,tab,access.permissions.join(',')]);
 async function waitTask(taskId){
  for(let i=0;i<30;i++){await new Promise(resolve=>setTimeout(resolve,700));const rows=await listServerTasks(server.id);setTasks(rows);const task=rows.find(t=>t.id===taskId);if(task&&(task.status==='completed'||task.status==='failed')){const detail=await getServerTask(server.id,taskId);if(task.status==='failed'||detail.result?.error)throw new Error(detail.result?.error||'Node operation failed');return detail.result?.data||{};}}
  throw new Error('Node did not respond in time. Check the node agent service.');
 }
 async function refreshBackupSchedules(){
  if(!can('server.manage'))return;
  try{setBackupSchedules(await listBackupSchedules(server.id));}catch(e){setError(e.message);}
 }
 async function addBackupSchedule(e){
  e.preventDefault();setBusy(true);setError('');
  try{await createBackupSchedule(server.id,{...scheduleForm,retention:Number(scheduleForm.retention)});await refreshBackupSchedules();announce('Automatic backup schedule created');}
  catch(e){setError(e.message);}finally{setBusy(false);}
 }
 async function toggleBackupSchedule(schedule){
  setBusy(true);setError('');
  try{await updateBackupSchedule(server.id,schedule.id,{enabled:!schedule.enabled});await refreshBackupSchedules();}
  catch(e){setError(e.message);}finally{setBusy(false);}
 }
 async function removeBackupSchedule(schedule){
  if(!window.confirm('Delete the '+schedule.name+' backup schedule? Existing backups will be kept.'))return;
  setBusy(true);setError('');
  try{await deleteBackupSchedule(server.id,schedule.id);await refreshBackupSchedules();announce('Backup schedule deleted');}
  catch(e){setError(e.message);}finally{setBusy(false);}
 }
 async function runBackup(action,backupId){
  const requiredPermission={list:'backup.read',create:'backup.create',restore:'backup.restore'}[action];
  if(!requiredPermission||!can(requiredPermission)){setError('Your account does not have permission to '+action+' backups.');return;}
  if(action==='restore'&&!window.confirm('Restore this snapshot? Current server data will first be saved as a safety backup.'))return;
  setBusy(true);setError('');
  try{
   const queued=await manageServerBackups(server.id,{action,backup_id:backupId});
   const data=await waitTask(queued.task_id);
   if(data.backups)setBackups(data.backups);
   else if(action==='restore'){const refreshed=await manageServerBackups(server.id,{action:'list'});const latest=await waitTask(refreshed.task_id);setBackups(latest.backups||[]);}
   if(action==='create')announce('Backup created on the VPS node');
   if(action==='restore')announce('Backup restored successfully');
  }catch(e){setError(e.message);}finally{setBusy(false);}
 }

 async function refreshMods(kind=modKind){
  setBusy(true);setError('');
  try{const queued=await manageServerMods(server.id,{action:'list',kind});const data=await waitTask(queued.task_id);setMods(data.files||[]);}
  catch(e){setError(e.message);}finally{setBusy(false);}
 }
 async function changeMod(action,filename){
  if(action==='remove'&&!window.confirm('Remove '+filename+' from this server?'))return;
  setBusy(true);setError('');
  try{
   const payload={action,kind:modKind,filename};
   if(action==='install')payload.url=modUrl;
   const queued=await manageServerMods(server.id,payload);const data=await waitTask(queued.task_id);
   setMods(data.files||[]);setModUrl('');setModFilename('');announce(action==='install'?'JAR installed. Restart may be required.':'JAR removed');
  }catch(e){setError(e.message);}finally{setBusy(false);}
 }
 async function runVersionUpgrade(){
  if(!window.confirm('Upgrade '+server.name+' to Minecraft '+versionChoice+'? The node creates a pre-upgrade backup first.'))return;
  setBusy(true);setError('');
  try{const queued=await upgradeServerVersion(server.id,versionChoice);await waitTask(queued.task_id);announce('Minecraft version upgraded to '+versionChoice);}
  catch(e){setError(e.message);}finally{setBusy(false);}
 }
 async function runMinecraft(payload){
  setBusy(true);setError('');
  try{const queued=await minecraftAction(server.id,payload);await waitTask(queued.task_id);await requestConsoleLogs(server.id);await refreshTasks();announce('Minecraft command delivered to node');}
  catch(e){setError(e.message);}finally{setBusy(false);}
 }
 async function sendCommand(e){
  e.preventDefault();if(!command.trim())return;setBusy(true);setError('');
  try{await sendConsoleCommand(server.id,command.trim());setCommand('');await refreshTasks();announce('Console command queued');}
  catch(e){setError(e.message);}finally{setBusy(false);}
 }
 async function fileOperation(operation,extra={}){
  const requiredPermission=['list','read'].includes(operation)?'file.read':'file.write';
  if(!can(requiredPermission)){setError('Your account does not have permission to '+operation+' server files.');return;}
  setBusy(true);setError('');
  try{
   const queued=await operateServerFiles(server.id,{operation,path,...extra});
   const data=await waitTask(queued.task_id);
   if(operation==='list'){setEntries(data.entries||[]);setPath(data.path||path);setFilePath('');}
   if(operation==='read'){const raw=atob(data.content_base64||'');const bytes=Uint8Array.from(raw,c=>c.charCodeAt(0));setFilePath(data.path);setFileText(new TextDecoder().decode(bytes));}
   if(operation==='write'){announce('File saved on VPS');const q=await operateServerFiles(server.id,{operation:'list',path});const listing=await waitTask(q.task_id);setEntries(listing.entries||[]);}
   if(['delete','rename','mkdir'].includes(operation)){const target=extra.parent||path;const q=await operateServerFiles(server.id,{operation:'list',path:target});const listing=await waitTask(q.task_id);setEntries(listing.entries||[]);setPath(listing.path||target);setFilePath('');}
  }catch(e){setError(e.message);}finally{setBusy(false);}
 }
 async function loadServerSettings(){
  if(!can('file.read'))return;
  setBusy(true);setError('');
  try{
   const queued=await operateServerFiles(server.id,{operation:'read',path:'server.properties'});
   const data=await waitTask(queued.task_id);
   const raw=atob(data.content_base64||'');const bytes=Uint8Array.from(raw,ch=>ch.charCodeAt(0));const content=new TextDecoder().decode(bytes);
   const values={...serverSettings};
   for(const line of content.split(/\r?\n/)){const trimmed=line.trim();if(!trimmed||trimmed.startsWith('#')||!trimmed.includes('='))continue;const index=trimmed.indexOf('=');const key=trimmed.slice(0,index).trim();if(Object.prototype.hasOwnProperty.call(values,key))values[key]=trimmed.slice(index+1).trim();}
   setServerSettings(values);setFilePath('server.properties');setFileText(content);setSettingsLoaded(true);
  }catch(e){setError('Could not load server.properties: '+e.message);}finally{setBusy(false);}
 }
 async function saveServerSettings(){
  if(!can('file.write'))return;
  setBusy(true);setError('');
  try{
   const keys=Object.keys(serverSettings);const seen=new Set();
   const lines=fileText.split(/\r?\n/).map(line=>{const trimmed=line.trim();if(!trimmed||trimmed.startsWith('#')||!trimmed.includes('='))return line;const index=trimmed.indexOf('=');const key=trimmed.slice(0,index).trim();if(!keys.includes(key))return line;seen.add(key);return key+'='+serverSettings[key];});
   for(const key of keys)if(!seen.has(key))lines.push(key+'='+serverSettings[key]);
   const content=lines.join('\n');const bytes=new TextEncoder().encode(content);let binary='';for(let i=0;i<bytes.length;i+=0x8000)binary+=String.fromCharCode(...bytes.subarray(i,i+0x8000));
   const queued=await operateServerFiles(server.id,{operation:'write',path:'server.properties',content_base64:btoa(binary)});
   await waitTask(queued.task_id);setFileText(content);announce('Server properties saved. Restart the server to apply all changes.');
  }catch(e){setError(e.message);}finally{setBusy(false);}
 }
 async function uploadFile(event){
  const file=event.target.files?.[0];event.target.value='';if(!file)return;
  if(file.size>512*1024){setError('Upload limit is 512 KB. Use SFTP for larger files.');return;}
  try{const bytes=new Uint8Array(await file.arrayBuffer());let binary='';for(let i=0;i<bytes.length;i+=0x8000)binary+=String.fromCharCode(...bytes.subarray(i,i+0x8000));await fileOperation('write',{path:path==='.'?file.name:path+'/'+file.name,content_base64:btoa(binary)});}catch(e){setError(e.message);}
 }
 async function downloadFile(){
  if(!filePath)return;
  setBusy(true);setError('');
  try{const q=await operateServerFiles(server.id,{operation:'read',path:filePath});const data=await waitTask(q.task_id);const raw=atob(data.content_base64||'');const bytes=Uint8Array.from(raw,c=>c.charCodeAt(0));const url=URL.createObjectURL(new Blob([bytes]));const link=document.createElement('a');link.href=url;link.download=filePath.split('/').pop();link.click();URL.revokeObjectURL(url);}catch(e){setError(e.message);}finally{setBusy(false);}
 }
 function encodeBase64(value){
  const bytes=new TextEncoder().encode(value);let binary='';
  for(let i=0;i<bytes.length;i+=0x8000)binary+=String.fromCharCode(...bytes.subarray(i,i+0x8000));
  return btoa(binary);
 }
 useEffect(()=>{if(tab==='files'&&(can('file.read')||can('file.write')))fileOperation('list');if(tab==='backups'){if(can('backup.read'))runBackup('list');if(can('server.manage'))refreshBackupSchedules();}if(tab==='mods'&&can('server.manage'))refreshMods(modKind);if(tab==='members'&&access.is_owner)refreshMembers();if(tab==='settings'&&can('file.read')&&!settingsLoaded)loadServerSettings();},[tab,server.id,access.is_owner,settingsLoaded]);
 const parent=path==='.'?'.':(path.includes('/')?path.split('/').slice(0,-1).join('/')||'.':'.');
 return <section className="server-workspace">
  <div className="workspace-head"><div><div className="eyebrow">SERVER CONTROL · #{server.id}</div><h2>{server.name}</h2><p>Minecraft Java · {server.version} · {server.status}</p></div><button className="button-secondary" onClick={onClose}><X size={15}/> Close</button></div>
  <div className="workspace-tabs">{can('server.read')&&<button className={tab==='overview'?'active':''} onClick={()=>setTab('overview')}><LayoutDashboard size={15}/> Overview</button>}{can('control.console')&&<button className={tab==='console'?'active':''} onClick={()=>setTab('console')}><Terminal size={15}/> Console</button>}{(can('file.read')||can('file.write'))&&<button className={tab==='files'?'active':''} onClick={()=>setTab('files')}><Folder size={15}/> File manager</button>}{can('server.manage')&&<button className={tab==='minecraft'?'active':''} onClick={()=>setTab('minecraft')}><Gamepad2 size={15}/> Minecraft</button>}{can('server.manage')&&<button className={tab==='mods'?'active':''} onClick={()=>setTab('mods')}><Box size={15}/> Plugins & mods</button>}{(can('backup.read')||can('backup.create')||can('backup.restore'))&&<button className={tab==='backups'?'active':''} onClick={()=>setTab('backups')}><HardDrive size={15}/> Backups</button>}{can('file.read')&&<button className={tab==='settings'?'active':''} onClick={()=>setTab('settings')}><Settings size={15}/> Settings</button>}{access.is_owner&&<button className={tab==='members'?'active':''} onClick={()=>setTab('members')}><Users size={15}/> Team access</button>}</div>
  {error&&<div className="auth-error">{error}</div>}
  {tab==='none'?<div className="backup-empty">Your account can view this server, but no control permissions have been granted.</div>:tab==='overview'&&can('server.read')?<div className="server-overview">
   <div className="server-overview-grid">
    <div className="server-overview-card"><span>SERVER STATUS</span><strong className={'server-overview-status '+(server.status==='online'?'is-online':'')}>{server.status}</strong><small>Current runtime state</small></div>
    <div className="server-overview-card"><span>MINECRAFT VERSION</span><strong>{server.version||'Latest'}</strong><small>Java Edition</small></div>
    <div className="server-overview-card"><span>MEMORY LIMIT</span><strong>{(server.memory_mb/1024).toFixed(1)} GB</strong><small>Configured allocation</small></div>
    <div className="server-overview-card"><span>CPU LIMIT</span><strong>{server.cpu_limit} vCPU</strong><small>Configured compute</small></div>
   </div>
   <div className="server-overview-lower">
    <div className="backup-card"><b>Server information</b><div className="server-info-line"><span>Server ID</span><code>#{server.id}</code></div><div className="server-info-line"><span>Node ID</span><code>#{server.node_id}</code></div><div className="server-info-line"><span>Allocation port</span><code>{server.allocation_port||'Not assigned'}</code></div><div className="server-info-line"><span>Created</span><code>{server.created_at?new Date(server.created_at).toLocaleString():'—'}</code></div></div>
    <div className="backup-card"><b>Recent operations</b><small>Latest actions recorded for this server</small>{tasks.slice(-5).reverse().map(task=><div className="server-info-line" key={task.id}><span>{task.action}</span><code>{task.status}</code></div>)}{tasks.length===0&&<div className="backup-empty">No operations have been recorded yet.</div>}</div>
   </div>
  </div>:tab==='members'&&access.is_owner?<div className="members-manager"><div className="backup-card"><b>Server team</b><small>Only existing LPGP accounts can be added. Access applies to this server only.</small>{membersLoading?<div className="backup-empty">Loading team…</div>:members.map(member=><div className="backup-row" key={member.id}><div className="backup-symbol"><Users size={16}/></div><div className="backup-meta"><b>{member.username}</b><small>{member.email} · {member.permissions.join(', ')}</small></div><button className="small-action danger" onClick={()=>revokeMember(member.id)}>Revoke</button></div>)}{!membersLoading&&members.length===0&&<div className="backup-empty">No team members have access yet.</div>}</div><div className="backup-card"><b>Grant server access</b><small>Choose the exact actions this account may perform.</small><form className="member-invite-form" onSubmit={inviteMember}><input type="email" value={memberEmail} onChange={e=>setMemberEmail(e.target.value)} placeholder="Existing account email" required/><div className="permission-grid">{[['server.read','View server and task history'],['control.console','Use console and view logs'],['control.start','Start server'],['control.stop','Stop server'],['control.restart','Restart server'],['file.read','Read and download files'],['file.write','Create, edit, rename and delete files'],['backup.read','View backups'],['backup.create','Create backups'],['backup.restore','Restore backups'],['server.manage','Minecraft controls and version upgrades']].map(([key,label])=><label key={key}><input type="checkbox" checked={memberPermissions.includes(key)} onChange={e=>setMemberPermissions(old=>e.target.checked?[...old,key]:old.filter(x=>x!==key))}/><span>{label}</span></label>)}</div><button className="button-primary" disabled={busy||!memberEmail||memberPermissions.length===0}><Plus size={14}/> Grant access</button></form></div></div>:tab==='settings'&&can('file.read')?<div className="server-settings-layout"><div className="backup-card"><div className="backup-heading"><div><b>Server properties</b><small>Saved to server.properties on the VPS. Restart the server to apply changes.</small></div><button className="small-action ghost" disabled={busy} onClick={loadServerSettings}><RefreshCw size={13}/> Reload</button></div>{!settingsLoaded?<div className="backup-empty">Loading server.properties…</div>:<div className="server-settings-grid"><label className="server-setting-wide">Server MOTD<input value={serverSettings.motd} maxLength={120} onChange={e=>setServerSettings(v=>({...v,motd:e.target.value}))}/></label><label>Maximum players<input type="number" min="1" max="1000" value={serverSettings['max-players']} onChange={e=>setServerSettings(v=>({...v,'max-players':e.target.value}))}/></label><label>Difficulty<select value={serverSettings.difficulty} onChange={e=>setServerSettings(v=>({...v,difficulty:e.target.value}))}><option>peaceful</option><option>easy</option><option>normal</option><option>hard</option></select></label><label>Default game mode<select value={serverSettings.gamemode} onChange={e=>setServerSettings(v=>({...v,gamemode:e.target.value}))}><option>survival</option><option>creative</option><option>adventure</option><option>spectator</option></select></label><label>Spawn protection<input type="number" min="0" max="128" value={serverSettings['spawn-protection']} onChange={e=>setServerSettings(v=>({...v,'spawn-protection':e.target.value}))}/></label><label>View distance<input type="number" min="2" max="32" value={serverSettings['view-distance']} onChange={e=>setServerSettings(v=>({...v,'view-distance':e.target.value}))}/></label><label>Simulation distance<input type="number" min="2" max="32" value={serverSettings['simulation-distance']} onChange={e=>setServerSettings(v=>({...v,'simulation-distance':e.target.value}))}/></label><label className="server-setting-toggle"><input type="checkbox" checked={serverSettings.pvp==='true'} onChange={e=>setServerSettings(v=>({...v,pvp:String(e.target.checked)}))}/> Enable PvP</label><label className="server-setting-toggle"><input type="checkbox" checked={serverSettings['white-list']==='true'} onChange={e=>setServerSettings(v=>({...v,'white-list':String(e.target.checked)}))}/> Enable whitelist</label></div>}{can('file.write')&&<div className="server-settings-actions"><button className="button-primary" disabled={busy||!settingsLoaded} onClick={saveServerSettings}><Save size={14}/> Save settings</button></div>}</div><div className="backup-card"><b>Security note</b><small>Authentication settings are intentionally not exposed here. Keep online authentication enabled and manage whitelist access from the Minecraft tab.</small></div></div>:tab==='console'?<div className="console-layout">
   <div className="console-screen"><div className="console-top"><span><i/> LIVE NODE OUTPUT</span><button onClick={()=>requestConsoleLogs(server.id).catch(e=>setError(e.message))}><RefreshCw size={13}/> Refresh</button></div><pre>{logs}</pre></div>
   <form className="console-command" onSubmit={sendCommand}><span className="console-prompt">/</span><input value={command} onChange={e=>setCommand(e.target.value)} placeholder="Enter a Minecraft command (e.g. list, say Hello)" maxLength={512}/><button className="button-primary" disabled={busy||!command.trim()}><Send size={14}/> Send</button></form>
   <div className="task-history"><b>Recent console actions</b>{tasks.filter(t=>t.action==='console').slice(-5).reverse().map(t=><div key={t.id}><code>{t.id}</code><span>{t.status==='completed'?'Command delivered':t.status==='failed'?'Failed':'Queued'}</span><small>{new Date(t.created_at).toLocaleTimeString()}</small></div>)}</div>
  </div>:tab==='minecraft'?<div className="minecraft-manager"><div className="minecraft-card"><div className="minecraft-card-head"><div><b>Players & permissions</b><small>Commands are executed by the Minecraft server process</small></div><button className="small-action" disabled={busy} onClick={()=>runMinecraft({action:'list'})}><RefreshCw size={13}/> Request player list</button></div><div className="minecraft-player-row"><input value={player} onChange={e=>setPlayer(e.target.value)} placeholder="Minecraft username" maxLength={16}/><button className="small-action" disabled={busy||player.trim().length<3} onClick={()=>runMinecraft({action:'whitelist_add',player:player.trim()})}>Whitelist</button><button className="small-action ghost" disabled={busy||player.trim().length<3} onClick={()=>runMinecraft({action:'whitelist_remove',player:player.trim()})}>Unwhitelist</button></div><div className="minecraft-player-row"><button className="small-action" disabled={busy||player.trim().length<3} onClick={()=>runMinecraft({action:'op',player:player.trim()})}>Make operator</button><button className="small-action danger" disabled={busy||player.trim().length<3} onClick={()=>runMinecraft({action:'deop',player:player.trim()})}>Remove operator</button><button className="small-action ghost" disabled={busy} onClick={()=>runMinecraft({action:'save_all'})}><Save size={13}/> Save world</button></div><small className="minecraft-note">Player-list results appear in the Console tab after the server responds. Username validation is enforced by the API.</small></div><div className="minecraft-card"><b>World configuration</b><small>Apply a preset directly to the running server</small><div className="minecraft-settings-grid"><label>Difficulty<select value={difficulty} onChange={e=>setDifficulty(e.target.value)}><option>peaceful</option><option>easy</option><option>normal</option><option>hard</option></select><button className="small-action" disabled={busy} onClick={()=>runMinecraft({action:'difficulty',value:difficulty})}>Apply</button></label><label>Default game mode<select value={gameMode} onChange={e=>setGameMode(e.target.value)}><option>survival</option><option>creative</option><option>adventure</option><option>spectator</option></select><button className="small-action" disabled={busy} onClick={()=>runMinecraft({action:'gamemode',value:gameMode})}>Apply</button></label><label>World time<select value={worldTime} onChange={e=>setWorldTime(e.target.value)}><option>day</option><option>noon</option><option>night</option><option>midnight</option></select><button className="small-action" disabled={busy} onClick={()=>runMinecraft({action:'time',value:worldTime})}>Apply</button></label><label>Weather<select value={weather} onChange={e=>setWeather(e.target.value)}><option>clear</option><option>rain</option><option>thunder</option></select><button className="small-action" disabled={busy} onClick={()=>runMinecraft({action:'weather',value:weather})}>Apply</button></label></div></div></div>:tab==='mods'&&can('server.manage')?<div className="backup-manager"><div className="backup-card"><div className="backup-heading"><div><b>Plugin & mod manager</b><small>Install direct JAR downloads from trusted Modrinth, Hangar and CurseForge CDN hosts. The server is stopped while files are changed.</small></div><button className="small-action ghost" disabled={busy} onClick={()=>refreshMods()}><RefreshCw size={13}/> Refresh</button></div><div className="version-controls"><select value={modKind} onChange={e=>{setModKind(e.target.value);refreshMods(e.target.value);}}><option value="plugin">Paper plugins</option><option value="mod">Fabric / Forge mods</option></select></div><form className="member-invite-form" onSubmit={e=>{e.preventDefault();changeMod('install',modFilename);}}><div className="user-form-grid"><input value={modFilename} onChange={e=>setModFilename(e.target.value)} placeholder="Plugin or mod filename.jar" pattern="[A-Za-z0-9_. -]+\.jar" required/><input value={modUrl} onChange={e=>setModUrl(e.target.value)} placeholder="Direct HTTPS JAR URL" type="url" required/></div><button className="button-primary" disabled={busy||!modFilename.toLowerCase().endsWith('.jar')||!modUrl.startsWith('https://')}><Plus size={14}/> Install JAR</button></form><div className="backup-list">{mods.map(item=><div className="backup-row" key={item.filename}><div className="backup-symbol"><FileCode size={16}/></div><div className="backup-meta"><b>{item.filename}</b><small>{(item.size_bytes/1048576).toFixed(2)} MB</small></div><button className="small-action danger" disabled={busy} onClick={()=>changeMod('remove',item.filename)}>Remove</button></div>)}{mods.length===0&&<div className="backup-empty">No JAR files found in this server's {modKind==='plugin'?'plugins':'mods'} folder.</div>}</div></div></div>:tab==='backups'?<div className="backup-manager"><div className="backup-card"><div className="backup-heading"><div><b>Restore points</b><small>Snapshots are stored on the VPS node, outside the server's Docker volume</small></div>{can('backup.create')&&<button className="small-action" disabled={busy} onClick={()=>runBackup('create')}><Plus size={13}/> Create backup</button>}</div><div className="backup-list">{!can('backup.read')?<div className="backup-empty">You can create or restore snapshots, but viewing the backup list requires backup.read access.</div>:backups.map(item=><div className="backup-row" key={item.id}><div className="backup-symbol"><HardDrive size={16}/></div><div className="backup-meta"><b>{item.created_at}</b><small>{item.id} · {(item.size_bytes/1048576).toFixed(1)} MB</small></div>{can('backup.restore')&&<button className="small-action ghost" disabled={busy} onClick={()=>runBackup('restore',item.id)}><RefreshCw size={13}/> Restore</button>}</div>)}{backups.length===0&&<div className="backup-empty">No snapshots found. Create your first backup before making major server changes.</div>}</div></div><div className="backup-card"><div className="backup-heading"><div><b>Automatic backups</b><small>Schedules run through your connected VPS node agent. Retention applies to scheduled snapshots only.</small></div></div>{can('server.manage')&&<form className="member-invite-form" onSubmit={addBackupSchedule}><div className="user-form-grid"><input value={scheduleForm.name} onChange={e=>setScheduleForm(v=>({...v,name:e.target.value}))} placeholder="Schedule name" minLength="2" maxLength="80" required/><select value={scheduleForm.frequency} onChange={e=>setScheduleForm(v=>({...v,frequency:e.target.value}))}><option value="hourly">Every hour</option><option value="daily">Every day</option><option value="weekly">Every week</option></select><label>Keep scheduled backups<input type="number" min="1" max="100" value={scheduleForm.retention} onChange={e=>setScheduleForm(v=>({...v,retention:e.target.value}))}/></label></div><button className="button-primary" disabled={busy}><Plus size={14}/> Add schedule</button></form>}{backupSchedules.map(schedule=><div className="backup-row" key={schedule.id}><div className="backup-symbol"><RefreshCw size={16}/></div><div className="backup-meta"><b>{schedule.name} · {schedule.frequency}</b><small>{schedule.enabled?'Enabled':'Paused'} · Keep {schedule.retention} · Next run {new Date(schedule.next_run_at).toLocaleString()}</small></div>{can('server.manage')&&<><button className="small-action ghost" disabled={busy} onClick={()=>toggleBackupSchedule(schedule)}>{schedule.enabled?'Pause':'Resume'}</button><button className="small-action danger" disabled={busy} onClick={()=>removeBackupSchedule(schedule)}>Delete</button></>}</div>)}{backupSchedules.length===0&&<div className="backup-empty">No automatic backup schedules configured.</div>}</div><div className="backup-card version-card"><b>Minecraft version</b><small>Upgrade uses the official itzg Minecraft server container and creates a pre-upgrade snapshot first. Server may be unavailable during the upgrade.</small><div className="version-controls"><select value={versionChoice} onChange={e=>setVersionChoice(e.target.value)}><option value="1.21.11">1.21.11</option><option value="1.21.4">1.21.4</option><option value="1.21.1">1.21.1</option><option value="1.20.4">1.20.4</option></select><button className="small-action" disabled={busy||versionChoice===server.version} onClick={runVersionUpgrade}><RefreshCw size={13}/> Upgrade version</button></div><small className="backup-warning">Back up important files separately too. Node-local snapshots do not protect against VPS disk loss.</small></div></div>:<div className="file-manager">
   <div className="file-toolbar"><div className="file-breadcrumb"><button onClick={()=>fileOperation('list',{path:'.'})}>/data</button>{path!=='.'&&<><ChevronRight size={13}/><span>{path}</span></>}</div><div><button className="small-action ghost" onClick={()=>fileOperation('list')}><RefreshCw size={13}/> Refresh</button>{can('file.write')&&<><label className="small-action file-upload-button"><input type="file" onChange={uploadFile} hidden/>Upload</label><button className="small-action" onClick={()=>{const name=window.prompt('New file name');if(name)fileOperation('write',{path:path==='.'?name:path+'/'+name,content_base64:''});}}><FilePlus size={13}/> New file</button><button className="small-action" onClick={()=>{const name=window.prompt('New folder name');if(name)fileOperation('mkdir',{path:path==='.'?name:path+'/'+name});}}><FolderPlus size={13}/> Folder</button></>}</div></div>
   <div className="file-columns"><div className="file-list">{path!=='.'&&<button className="file-row" onClick={()=>fileOperation('list',{path:parent})}><ArrowLeft size={14}/> ..</button>}{entries.map(entry=><button className="file-row" key={entry.path} onClick={()=>entry.directory?fileOperation('list',{path:entry.path}):fileOperation('read',{path:entry.path})}>{entry.directory?<Folder size={15}/>:<FileCode size={15}/>}<span>{entry.name}</span><small>{entry.directory?'Folder':(entry.size/1024).toFixed(1)+' KB'}</small></button>)}</div>
    <div className="file-editor">{filePath?<><div className="editor-head"><b>{filePath}</b><div>{can('file.read')&&<button className="small-action ghost" disabled={busy} onClick={downloadFile}><Download size={13}/> Download</button>}{can('file.write')&&<><button className="small-action" disabled={busy} onClick={()=>fileOperation('write',{path:filePath,content_base64:encodeBase64(fileText)})}><Save size={13}/> Save</button><button className="small-action danger" disabled={busy} onClick={()=>{if(window.confirm('Delete '+filePath+'?'))fileOperation('delete',{path:filePath});}}><Trash2 size={13}/> Delete</button></>}</div></div><textarea spellCheck="false" value={fileText} onChange={e=>setFileText(e.target.value)}/></>:<div className="file-empty"><Folder size={28}/><b>Select a file to edit</b><span>Files up to 512 KB can be edited here. Use SFTP for larger files.</span></div>}</div>
   </div>
  </div>}
  {busy&&<div className="workspace-busy"><LoaderCircle size={14}/> Waiting for node agent…</div>}
 </section>;
}

function ActivityLogsPage(){
 const [events,setEvents]=useState([]),[loading,setLoading]=useState(true),[error,setError]=useState(''),[filter,setFilter]=useState('');
 async function refresh(){
  setLoading(true);setError('');
  try{const rows=await listAudit();setEvents(Array.isArray(rows)?rows:[]);}
  catch(e){setError(e.message);}
  finally{setLoading(false);}
 }
 useEffect(()=>{refresh();},[]);
 const visible=events.filter(event=>[event.action,event.detail,event.actor_username,event.actor_id].filter(Boolean).join(' ').toLowerCase().includes(filter.toLowerCase()));
 return <div className="panel audit-page">
  <div className="panel-head"><div><h3>Activity log</h3><p>Administrative events recorded by the LPGP API</p></div><span className="audit-count">{events.length} EVENTS</span></div>
  {error&&<div className="auth-error">{error}</div>}
  <div className="audit-toolbar"><div className="search-box"><Search size={15}/><input value={filter} onChange={e=>setFilter(e.target.value)} placeholder="Filter by action, actor or details…"/></div><button className="small-action ghost" disabled={loading} onClick={refresh}><RefreshCw size={13}/> {loading?'Refreshing…':'Refresh'}</button></div>
  {loading?<div className="empty">Loading audit events…</div>:<div className="audit-list">{visible.map((event,index)=><article className="audit-event" key={event.id||index}><span className="audit-event-icon"><Activity size={15}/></span><div className="audit-event-main"><b>{event.action||'Activity'}</b><p>{event.detail||'No additional details recorded.'}</p><small>{event.actor_username||(event.actor_id?`User #${event.actor_id}`:'System')}</small></div><time>{event.created_at?new Date(event.created_at).toLocaleString():'—'}</time></article>)}{visible.length===0&&<div className="empty">{events.length?'No events match this filter.':'No audit events have been recorded yet.'}</div>}</div>}
 </div>;
}

function UsersPage({announce}){
 const [users,setUsers]=useState([]),[loading,setLoading]=useState(true),[error,setError]=useState(''),[show,setShow]=useState(false);
 const [form,setForm]=useState({email:'',username:'',password:'',role:'user'});
 const refresh=()=>{setLoading(true);listUsers().then(setUsers).catch(e=>setError(e.message)).finally(()=>setLoading(false));};
 useEffect(()=>{refresh();},[]);
 async function submit(e){e.preventDefault();try{await createUser(form);setShow(false);setForm({email:'',username:'',password:'',role:'user'});setError('');refresh();announce('Account created successfully');}catch(e){setError(e.message);}}
 async function toggle(u){try{await setUserStatus(u.id,!u.is_active);refresh();}catch(e){setError(e.message);}}
 return <div className="panel servers-page"><div className="panel-head"><div><h3>Account directory</h3><p>Live accounts retrieved from the authenticated API</p></div><button className="button-primary" onClick={()=>setShow(v=>!v)}><Plus size={16}/> Add user</button></div>
 {error&&<div className="auth-error">{error}</div>}{loading?<p className="muted">Loading users from API…</p>:<div className="table-wrap"><table><thead><tr><th>ACCOUNT</th><th>ROLE</th><th>STATUS</th><th>CREATED</th><th>ACTION</th></tr></thead><tbody>{users.map(u=><tr key={u.id}><td><b>{u.username}</b><small className="user-email">{u.email}</small></td><td>{u.role}</td><td><span className={'server-status '+(u.is_active?'online':'offline')}><i/>{u.is_active?'Active':'Disabled'}</span></td><td>{new Date(u.created_at).toLocaleDateString()}</td><td><button className="small-action" onClick={()=>toggle(u)}>{u.is_active?'Disable':'Enable'}</button></td></tr>)}</tbody></table>{users.length===0&&<div className="empty">No accounts found.</div>}</div>}
 {show&&<form className="user-create-form" onSubmit={submit}><h3>Create account</h3><div className="user-form-grid"><input type="email" placeholder="Email address" value={form.email} onChange={e=>setForm({...form,email:e.target.value})} required/><input placeholder="Username" minLength="3" maxLength="32" value={form.username} onChange={e=>setForm({...form,username:e.target.value})} required/><input type="password" placeholder="Password (12+ characters)" minLength="12" value={form.password} onChange={e=>setForm({...form,password:e.target.value})} required/><select value={form.role} onChange={e=>setForm({...form,role:e.target.value})}><option value="user">User</option><option value="admin">Admin</option></select></div><button className="button-primary">Create account</button></form>}
 </div>;
}

function NodesPage({announce}){
 const [nodes,setNodes]=useState([]),[loading,setLoading]=useState(true),[error,setError]=useState(''),[show,setShow]=useState(false),[created,setCreated]=useState(null);
 const [form,setForm]=useState({name:'',fqdn:''});
 const refresh=()=>{setLoading(true);listNodes().then(setNodes).catch(e=>setError(e.message)).finally(()=>setLoading(false));};
 useEffect(()=>{refresh();},[]);
 async function submit(e){e.preventDefault();try{const result=await createNode(form);setCreated(result);setShow(false);setForm({name:'',fqdn:''});setError('');refresh();}catch(e){setError(e.message);}}
 async function toggle(n){try{await setNodeStatus(n.id,!n.is_enabled);refresh();}catch(e){setError(e.message);}}
 async function rotate(n){if(!window.confirm('Rotate the credential for '+n.name+'? The current node token will stop working immediately. You must update NODE_TOKEN in the VPS agent configuration and restart the agent.'))return;try{const result=await rotateNodeToken(n.id);setCreated({...result,rotated:true});setError('');}catch(e){setError(e.message);}}
 const online=n=>n.last_heartbeat&&Date.now()-new Date(n.last_heartbeat).getTime()<60000;
 return <div className="panel servers-page"><div className="panel-head"><div><h3>VPS node fleet</h3><p>Live telemetry from enrolled Lighting Node Agents</p></div><button className="button-primary" onClick={()=>setShow(v=>!v)}><Plus size={16}/> Enroll node</button></div>
 {error&&<div className="auth-error">{error}</div>}
 {created&&<div className="node-token-box"><b>{created.rotated?'Node token rotated — copy the new token now':'Node enrolled — copy this token now'}</b><p>{created.rotated?'The previous token is invalid immediately. Update NODE_TOKEN in the VPS agent config and restart the lighting agent before it can reconnect.':'The token is shown once. Store it securely and provide it to the node installer.'}</p><code>{created.token}</code><button className="small-action" onClick={()=>navigator.clipboard.writeText(created.token)}>Copy token</button><button className="small-action ghost" onClick={()=>setCreated(null)}>Dismiss</button></div>}
 {show&&<form className="user-create-form" onSubmit={submit}><h3>Enroll a VPS node</h3><div className="user-form-grid"><input placeholder="Node name (e.g. vps-01)" value={form.name} onChange={e=>setForm({...form,name:e.target.value})} required/><input placeholder="Node hostname / FQDN" value={form.fqdn} onChange={e=>setForm({...form,fqdn:e.target.value})} required/></div><button className="button-primary">Generate enrollment token</button></form>}
 {loading?<p className="muted">Loading node inventory…</p>:<div className="table-wrap"><table><thead><tr><th>NODE</th><th>CONNECTION</th><th>CPU</th><th>MEMORY</th><th>DISK</th><th>LAST HEARTBEAT</th><th>ACTION</th></tr></thead><tbody>{nodes.map(n=><tr key={n.id}><td><b>{n.name}</b><small className="user-email">{n.fqdn}</small></td><td><span className={'server-status '+(online(n)?'online':'offline')}><i/>{!n.is_enabled?'Disabled':online(n)?'Connected':'Offline'}</span></td><td>{n.cpu_percent.toFixed(1)}%</td><td>{(n.memory_used/1073741824).toFixed(1)} / {(n.memory_total/1073741824).toFixed(1)} GB</td><td>{(n.disk_used/1073741824).toFixed(1)} / {(n.disk_total/1073741824).toFixed(1)} GB</td><td>{n.last_heartbeat?new Date(n.last_heartbeat).toLocaleString():'Never'}</td><td><div className="node-row-actions"><button className="small-action" onClick={()=>toggle(n)}>{n.is_enabled?'Disable':'Enable'}</button><button className="small-action ghost" onClick={()=>rotate(n)}>Rotate token</button></div></td></tr>)}</tbody></table>{nodes.length===0&&<div className="empty">No nodes enrolled yet. Add your first VPS to start receiving telemetry.</div>}</div>}
 </div>;
}

function App(){
 const [user,setUser]=useState(null);
 const [checking,setChecking]=useState(Boolean(sessionStorage.getItem('lighting_panel_access_token')));
 useEffect(()=>{if(checking)currentUser().then(setUser).catch(()=>{clearToken();setUser(null);}).finally(()=>setChecking(false));},[]);
 async function signOut(){try{await logout();}catch{}setUser(null);}
 if(checking)return <div className="auth-loading"><Zap size={24}/> Checking secure session…</div>;
 return user?<DashboardApp user={user} onLogout={signOut}/>:<Login onLogin={setUser}/>;
}
export default App;

