import React, { useEffect, useMemo, useState } from 'react';
import Login from './Login.jsx';
import { currentUser, clearToken, logout, listUsers, createUser, setUserStatus, listAudit, listNodes, createNode, setNodeStatus, listServers, createGameServer, controlServer } from './api.js';
import { motion, AnimatePresence } from 'framer-motion';
import { Activity, ArrowDownToLine, ArrowUpRight, Bell, Box, ChartNoAxesCombined, ChevronDown, CircleHelp, Command, Cpu, Database, FileText, Gamepad2, Gauge, HardDrive, LayoutDashboard, LifeBuoy, LogOut, Menu, MoreHorizontal, Network, Plus, Search, Server, Settings, ShieldCheck, Terminal, Users, Wallet, Wifi, X, Zap } from 'lucide-react';

const initialServers = [];
const nav = [
 {title:'OVERVIEW',items:[['Dashboard',LayoutDashboard],['Servers',Server],['Databases',Database],['Backups',HardDrive]]},
 {title:'MANAGEMENT',items:[['Users',Users],['Nodes',Network],['Allocations',Box],['Activity Logs',FileText]]},
 {title:'SYSTEM',items:[['Admin Settings',Settings],['Security',ShieldCheck],['Support',LifeBuoy]]}
];
function Meter({value,color='purple'}) { return <div className="meter"><span className={color} style={{width:value+'%'}}/></div>; }
function Stat({icon:Icon,label,value,detail,trend}) { return <div className="stat-card"><div className="stat-top"><span className="stat-icon"><Icon size={17}/></span><span className="stat-trend">{trend}</span></div><div className="stat-value">{value}</div><div className="stat-label">{label}</div><div className="stat-detail">{detail}</div></div>; }
function DashboardApp({user,onLogout}){
 const [page,setPage]=useState('Dashboard'); const [servers,setServers]=useState(initialServers); const [nodes,setNodes]=useState([]); const [auditEvents,setAuditEvents]=useState([]); const [selected,setSelected]=useState(null); const [query,setQuery]=useState(''); const [sidebar,setSidebar]=useState(false); const [notice,setNotice]=useState(''); const [showCreate,setShowCreate]=useState(false); const [newName,setNewName]=useState('');
 useEffect(()=>{
  let alive=true;
  const load=async()=>{
   try{
    const [rows,nodeRows,auditRows]=await Promise.all([listServers(),listNodes(),listAudit()]);
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
      disk:0,players:'—',address:(node?.fqdn||'node')+':'+server.allocation_port,color:'violet'};
    }));
   }catch(error){if(alive)setNotice(error.message);}
  };
  load();const timer=setInterval(load,12000);
  return()=>{alive=false;clearInterval(timer);};
 },[]);
 const totalMemory=nodes.reduce((sum,n)=>sum+n.memory_total,0);
 const usedMemory=nodes.reduce((sum,n)=>sum+n.memory_used,0);
 const totalDisk=nodes.reduce((sum,n)=>sum+n.disk_total,0);
 const usedDisk=nodes.reduce((sum,n)=>sum+n.disk_used,0);
 const averageCpu=nodes.length?nodes.reduce((sum,n)=>sum+n.cpu_percent,0)/nodes.length:0;
 const memoryPercent=totalMemory?Math.min(100,Math.round(usedMemory/totalMemory*100)):0;
 const allocatedMemory=servers.reduce((sum,server)=>sum+(server.ram?server.ram:0),0);
 const diskPercent=totalDisk?Math.min(100,Math.round(usedDisk/totalDisk*100)):0;
 const active=servers.find(s=>s.id===selected)||servers[0];
 const filtered=useMemo(()=>servers.filter(s=>s.name.toLowerCase().includes(query.toLowerCase())),[servers,query]);
 const announce=(msg)=>{setNotice(msg);setTimeout(()=>setNotice(''),2600)};
 const toggleServer=(id)=>setServers(old=>old.map(s=>s.id===id?{...s,status:s.status==='Online'?'Offline':'Online',cpu:s.status==='Online'?0:Math.floor(15+Math.random()*25)}:s));
 const createServer=(e)=>{e.preventDefault();if(!newName.trim())return;const s={id:'srv-'+Date.now(),name:newName.trim(),game:'Minecraft Java',node:'Unassigned',status:'Offline',cpu:0,ram:0,disk:0,players:'—',address:'Not allocated',color:'violet'};setServers(old=>[...old,s]);setSelected(s.id);setNewName('');setShowCreate(false);setPage('Servers');announce('Server created in local demo state');};
 return <div className="app-shell">
  <aside className={'sidebar '+(sidebar?'sidebar-open':'')}><div className="brand"><div className="brand-mark"><Zap size={22} fill="currentColor"/></div><div><b>LIGHTING<span>PANEL</span></b><small>GAME SERVER CONTROL</small></div><button className="mobile-close" onClick={()=>setSidebar(false)}><X size={18}/></button></div>
   <div className="workspace"><div className="workspace-avatar">L</div><div><b>Lighting Network</b><small>Administrator workspace</small></div><ChevronDown size={15}/></div>
   <nav>{nav.map(group=><div className="nav-group" key={group.title}><div className="nav-heading">{group.title}</div>{group.items.map(([label,Icon])=><button key={label} className={'nav-link '+(page===label?'active':'')} onClick={()=>{setPage(label);setSidebar(false)}}><Icon size={17}/><span>{label}</span>{label==='Servers'&&<i>{servers.length}</i>}</button>)}</div>)}</nav>
   <div className="sidebar-bottom"><div className="promo-card"><div className="promo-icon"><Zap size={17}/></div><b>Power your community</b><p>Your infrastructure, one beautiful control plane.</p><button onClick={()=>announce('Documentation will be connected in a later phase')}>Explore features <ArrowUpRight size={14}/></button></div><div className="profile"><div className="avatar">A</div><div className="profile-name"><b>{user?.username || 'Administrator'}</b><small>{user?.email || 'Admin account'}</small></div><MoreHorizontal size={18}/></div></div>
  </aside>
  {sidebar&&<div className="scrim" onClick={()=>setSidebar(false)}/>}
  <main className="main"><header className="topbar"><div className="crumb"><button className="mobile-menu" onClick={()=>setSidebar(true)}><Menu size={19}/></button><span>Workspace</span><b>/</b><strong>{page}</strong></div><div className="top-actions"><div className="status-pill"><span/>All systems operational</div><button className="icon-button" onClick={()=>announce('You are all caught up')}><Bell size={18}/><i/></button><button className="help-button" onClick={onLogout}><LogOut size={16}/> <span>Sign out</span></button><button className="help-button" onClick={()=>announce('Help center coming soon')}><CircleHelp size={17}/> <span>Help</span></button></div></header>
  <div className="content"><div className="welcome-row"><div><div className="eyebrow"><span/> CONTROL CENTER <span className="eyebrow-line"/></div><h1>{page==='Dashboard'?'Welcome back, Admin.':page}</h1><p>{page==='Dashboard'?'Here’s what’s happening across your infrastructure today.':'Manage your Lighting Panel infrastructure and services.'}</p></div><div className="welcome-actions"><button className="button-secondary" onClick={()=>announce('Activity report export is not connected yet')}><ArrowDownToLine size={16}/> Export report</button><button className="button-primary" onClick={()=>setPage('Servers')}><Plus size={17}/> Create server</button></div></div>
  {page==='Dashboard'?<>
   <div className="stats-grid"><Stat icon={Server} label="Total servers" value={String(servers.length).padStart(2,'0')} detail="Across all nodes" trend="↗ Live"/><Stat icon={Activity} label="Running servers" value={String(servers.filter(s=>s.status==='Online').length).padStart(2,'0')} detail="Ready to serve players" trend="● Healthy"/><Stat icon={Cpu} label="CPU utilization" value={averageCpu.toFixed(1)+"%"} detail={nodes.length+" reporting nodes"} trend="↗ Live"/><Stat icon={Database} label="Memory allocated" value={allocatedMemory.toFixed(1)+" GB"} detail={servers.length+" server allocations"} trend="↗ Live"/></div>
   <div className="section-heading"><div><h2>Infrastructure</h2><p>Real-time overview of your server fleet</p></div><button className="text-button" onClick={()=>setPage('Servers')}>View all servers <ArrowUpRight size={15}/></button></div>
   <div className="overview-grid"><div className="panel fleet-panel"><div className="panel-head"><div><h3>Server overview</h3><p>Your recently active instances</p></div><button className="dots" onClick={()=>announce('More server actions coming soon')}><MoreHorizontal size={19}/></button></div><div className="server-list">{servers.slice(0,3).map(s=><div className="server-row" key={s.id}><div className={'server-icon '+s.color}><Gamepad2 size={19}/></div><div className="server-info"><b>{s.name}</b><small>{s.game} · {s.node}</small></div><div className={'server-status '+(s.status==='Online'?'online':'offline')}><i/>{s.status}</div><div className="server-usage"><span>CPU <b>{s.cpu}%</b></span><Meter value={s.cpu}/></div><button className="row-arrow" onClick={()=>{setSelected(s.id);setPage('Servers')}}><ArrowUpRight size={17}/></button></div>)}</div><button className="view-servers" onClick={()=>setPage('Servers')}>Manage all servers <ArrowUpRight size={15}/></button></div>
    <div className="panel capacity-panel"><div className="panel-head"><div><h3>Node capacity</h3><p>Combined resource allocation</p></div><span className="live-tag"><i/> LIVE</span></div><div className="capacity-total"><div><strong>{(totalMemory/1024**3).toFixed(1)} <small>GB</small></strong><span>Total memory</span></div><div className="capacity-ring" style={{background:"conic-gradient(#9274ff 0 "+memoryPercent+"%,#292c40 "+memoryPercent+"% 100%)"}}><div><b>{memoryPercent}%</b><small>USED</small></div></div></div><div className="capacity-bars"><div><div><span><i className="legend purple-bg"/>Memory</span><b>{(usedMemory/1024**3).toFixed(1)} / {(totalMemory/1024**3).toFixed(1)} GB</b></div><Meter value={memoryPercent}/></div><div><div><span><i className="legend cyan-bg"/>Storage</span><b>{(usedDisk/1024**3).toFixed(1)} / {(totalDisk/1024**3).toFixed(1)} GB</b></div><Meter value={diskPercent} color="cyan"/></div><div><div><span><i className="legend orange-bg"/>CPU</span><b>{averageCpu.toFixed(1)}% average</b></div><Meter value={averageCpu} color="orange"/></div></div></div></div>
   <div className="bottom-grid"><div className="panel activity-panel"><div className="panel-head"><div><h3>Recent activity</h3><p>Latest events from your panel</p></div><button className="text-button" onClick={()=>setPage('Activity Logs')}>View logs <ArrowUpRight size={14}/></button></div>{auditEvents.slice(0,4).map(event=><div className="activity-item" key={event.id}><span className="activity-dot purple-dot"><Activity size={14}/></span><div><b>{event.action}</b><small>{event.detail}</small></div><time>{new Date(event.created_at).toLocaleString()}</time></div>)}{auditEvents.length===0&&<div className="empty">No recorded activity yet.</div>}</div><div className="panel quick-panel"><div className="panel-head"><div><h3>Quick actions</h3><p>Jump into your workflow</p></div></div><div className="quick-grid"><button onClick={()=>setPage('Servers')}><span><Plus size={18}/></span><b>New server</b><small>Deploy an instance</small></button><button onClick={()=>setPage('Nodes')}><span><Network size={18}/></span><b>Add node</b><small>Expand infrastructure</small></button><button onClick={()=>setPage('Users')}><span><Users size={18}/></span><b>Invite user</b><small>Manage your team</small></button><button onClick={()=>setPage('Activity Logs')}><span><Terminal size={18}/></span><b>View logs</b><small>Inspect system events</small></button></div></div></div>
  </>:page==='Servers'?<RealServersPage announce={announce}/>:page==='Users'?<UsersPage announce={announce}/>:page==='Nodes'?<NodesPage announce={announce}/>:<div className="panel placeholder-page"><div className="placeholder-icon"><Command size={28}/></div><h2>{page}</h2><p>This module is part of the Lighting Panel roadmap. The dashboard and server-list demo are ready to explore.</p><button className="button-primary" onClick={()=>setPage('Dashboard')}>Back to dashboard</button></div>}
  <footer><span>© 2026 Lighting Panel</span><span><i/> All systems operational</span><span>Built for your infrastructure <Zap size={12}/></span></footer></div></main>
  <AnimatePresence>{showCreate&&<motion.div className="modal-backdrop" initial={{opacity:0}} animate={{opacity:1}} exit={{opacity:0}} onClick={()=>setShowCreate(false)}><motion.form className="modal" initial={{y:18,opacity:0}} animate={{y:0,opacity:1}} exit={{y:18,opacity:0}} onClick={e=>e.stopPropagation()} onSubmit={createServer}><button type="button" className="modal-close" onClick={()=>setShowCreate(false)}><X size={18}/></button><div className="modal-symbol"><Server size={22}/></div><h2>Create a server</h2><p>Give your new instance a name. Deployment configuration will be added in the node/daemon phase.</p><label>Server name</label><input autoFocus placeholder="e.g. Survival SMP" value={newName} onChange={e=>setNewName(e.target.value)} required maxLength={48}/><div className="modal-actions"><button type="button" className="button-secondary" onClick={()=>setShowCreate(false)}>Cancel</button><button className="button-primary" type="submit"><Plus size={16}/> Create server</button></div></motion.form></motion.div>}</AnimatePresence>
  <AnimatePresence>{notice&&<motion.div className="toast" initial={{opacity:0,y:12}} animate={{opacity:1,y:0}} exit={{opacity:0,y:12}}><ShieldCheck size={17}/>{notice}</motion.div>}</AnimatePresence>
 </div>
}


function RealServersPage({announce}){
 const [servers,setServers]=useState([]),[nodes,setNodes]=useState([]),[loading,setLoading]=useState(true),[error,setError]=useState(''),[saving,setSaving]=useState(false),[query,setQuery]=useState(''),[show,setShow]=useState(false);
 const [form,setForm]=useState({name:'',node_id:'',version:'LATEST',memory_mb:2048,cpu_limit:2});
 async function refresh(){
  try{const [serverRows,nodeRows]=await Promise.all([listServers(),listNodes()]);setServers(serverRows);setNodes(nodeRows);setError('');}
  catch(e){setError(e.message);}
  finally{setLoading(false);}
 }
 useEffect(()=>{refresh();const timer=setInterval(refresh,8000);return()=>clearInterval(timer);},[]);
 const filtered=servers.filter(s=>s.name.toLowerCase().includes(query.toLowerCase()));
 async function submit(e){
  e.preventDefault();setSaving(true);setError('');
  try{await createGameServer({...form,node_id:Number(form.node_id),memory_mb:Number(form.memory_mb),cpu_limit:Number(form.cpu_limit)});setShow(false);setForm({name:'',node_id:'',version:'LATEST',memory_mb:2048,cpu_limit:2});await refresh();announce('Server provisioning queued on VPS node');}
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
  <div className="panel-head"><div><h3>Minecraft servers</h3><p>Docker-backed instances provisioned on your connected VPS nodes</p></div><button className="button-primary" onClick={()=>setShow(v=>!v)}><Plus size={16}/> Deploy server</button></div>
  {error&&<div className="auth-error">{error}</div>}
  {show&&<form className="user-create-form" onSubmit={submit}><h3>Deploy Minecraft Java server</h3><div className="user-form-grid">
   <input placeholder="Server name" minLength="3" maxLength="48" value={form.name} onChange={e=>setForm({...form,name:e.target.value})} required/>
   <select value={form.node_id} onChange={e=>setForm({...form,node_id:e.target.value})} required><option value="">Choose online node</option>{nodes.filter(n=>n.is_enabled&&online(n)).map(n=><option key={n.id} value={n.id}>{n.name} · {n.fqdn}</option>)}</select>
   <select value={form.version} onChange={e=>setForm({...form,version:e.target.value})}><option value="LATEST">Latest Minecraft</option><option value="1.21.4">1.21.4</option><option value="1.21.1">1.21.1</option><option value="1.20.4">1.20.4</option></select>
   <select value={form.memory_mb} onChange={e=>setForm({...form,memory_mb:Number(e.target.value)})}><option value={1024}>1 GB RAM</option><option value={2048}>2 GB RAM</option><option value={4096}>4 GB RAM</option><option value={6144}>6 GB RAM</option><option value={8192}>8 GB RAM</option></select>
   <select value={form.cpu_limit} onChange={e=>setForm({...form,cpu_limit:Number(e.target.value)})}><option value={1}>1 vCPU</option><option value={2}>2 vCPU</option><option value={3}>3 vCPU</option><option value={4}>4 vCPU</option></select>
  </div><p className="muted">Creates a persistent Docker container with a dedicated TCP allocation. The node must be online and have enough free RAM.</p><button className="button-primary" disabled={saving||nodes.filter(n=>n.is_enabled&&online(n)).length===0}>{saving?'Queueing deployment…':'Deploy Minecraft server'}</button></form>}
  <div className="toolbar"><div className="search-box"><Search size={16}/><input placeholder="Search your servers…" value={query} onChange={e=>setQuery(e.target.value)}/></div><span className="muted">{servers.length} deployed</span></div>
  {loading?<p className="muted">Loading server inventory from API…</p>:<div className="table-wrap"><table><thead><tr><th>SERVER</th><th>NODE</th><th>STATUS</th><th>RESOURCES</th><th>ALLOCATION</th><th>CONTROLS</th></tr></thead><tbody>{filtered.map(server=>{const node=nodeById(server.node_id);const busy=['installing','starting','stopping','deleting'].includes(server.status);return <tr key={server.id}><td><div className="table-server"><span className="server-icon violet"><Gamepad2 size={17}/></span><span><b>{server.name}</b><small>Minecraft Java · {server.version}</small></span></div></td><td>{node?.name||'Unknown node'}<small className="user-email">{node?.fqdn||'—'}</small></td><td><span className={'server-status '+(server.status==='online'?'online':['installing','starting','stopping','deleting'].includes(server.status)?'installing':'offline')}><i/>{statusLabel(server.status)}</span>{server.last_error&&<small className="server-error">{server.last_error}</small>}</td><td>{server.memory_mb} MB RAM · {server.cpu_limit} vCPU</td><td><code>{node?.fqdn||'node'}:{server.allocation_port}</code></td><td><div className="server-controls"><button className="small-action" disabled={busy||server.status==='error'} onClick={()=>action(server,server.status==='online'?'stop':'start')}>{server.status==='online'?'Stop':'Start'}</button><button className="small-action ghost" disabled={busy||server.status==='error'} onClick={()=>action(server,'restart')}>Restart</button><button className="small-action danger" disabled={busy} onClick={()=>action(server,'delete')}>Delete</button></div></td></tr>})}</tbody></table>{filtered.length===0&&<div className="empty">{servers.length?'No servers match your search.':'No servers deployed yet. Enroll an online VPS node, then deploy your first Minecraft server.'}</div>}</div>}
 </div>;
}
\nfunction UsersPage({announce}){
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
 const online=n=>n.last_heartbeat&&Date.now()-new Date(n.last_heartbeat).getTime()<60000;
 return <div className="panel servers-page"><div className="panel-head"><div><h3>VPS node fleet</h3><p>Live telemetry from enrolled Lighting Node Agents</p></div><button className="button-primary" onClick={()=>setShow(v=>!v)}><Plus size={16}/> Enroll node</button></div>
 {error&&<div className="auth-error">{error}</div>}
 {created&&<div className="node-token-box"><b>Node enrolled — copy this token now</b><p>The token is shown once. Store it securely and provide it to the node installer.</p><code>{created.token}</code><button className="small-action" onClick={()=>navigator.clipboard.writeText(created.token)}>Copy token</button><button className="small-action ghost" onClick={()=>setCreated(null)}>Dismiss</button></div>}
 {show&&<form className="user-create-form" onSubmit={submit}><h3>Enroll a VPS node</h3><div className="user-form-grid"><input placeholder="Node name (e.g. vps-01)" value={form.name} onChange={e=>setForm({...form,name:e.target.value})} required/><input placeholder="Node hostname / FQDN" value={form.fqdn} onChange={e=>setForm({...form,fqdn:e.target.value})} required/></div><button className="button-primary">Generate enrollment token</button></form>}
 {loading?<p className="muted">Loading node inventory…</p>:<div className="table-wrap"><table><thead><tr><th>NODE</th><th>CONNECTION</th><th>CPU</th><th>MEMORY</th><th>DISK</th><th>LAST HEARTBEAT</th><th>ACTION</th></tr></thead><tbody>{nodes.map(n=><tr key={n.id}><td><b>{n.name}</b><small className="user-email">{n.fqdn}</small></td><td><span className={'server-status '+(online(n)?'online':'offline')}><i/>{!n.is_enabled?'Disabled':online(n)?'Connected':'Offline'}</span></td><td>{n.cpu_percent.toFixed(1)}%</td><td>{(n.memory_used/1073741824).toFixed(1)} / {(n.memory_total/1073741824).toFixed(1)} GB</td><td>{(n.disk_used/1073741824).toFixed(1)} / {(n.disk_total/1073741824).toFixed(1)} GB</td><td>{n.last_heartbeat?new Date(n.last_heartbeat).toLocaleString():'Never'}</td><td><button className="small-action" onClick={()=>toggle(n)}>{n.is_enabled?'Disable':'Enable'}</button></td></tr>)}</tbody></table>{nodes.length===0&&<div className="empty">No nodes enrolled yet. Add your first VPS to start receiving telemetry.</div>}</div>}
 </div>;
}
\nfunction App(){
 const [user,setUser]=useState(null);
 const [checking,setChecking]=useState(Boolean(sessionStorage.getItem('lighting_panel_access_token')));
 useEffect(()=>{if(checking)currentUser().then(setUser).catch(()=>{clearToken();setUser(null);}).finally(()=>setChecking(false));},[]);
 async function signOut(){try{await logout();}catch{}setUser(null);}
 if(checking)return <div className="auth-loading"><Zap size={24}/> Checking secure session…</div>;
 return user?<DashboardApp user={user} onLogout={signOut}/>:<Login onLogin={setUser}/>;
}
export default App;

