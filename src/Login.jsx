import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { Zap, LockKeyhole, Mail, ArrowRight, ShieldCheck, Activity } from 'lucide-react';
import { login } from './api.js';

export default function Login({ onLogin }) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  async function submit(event) {
    event.preventDefault(); setBusy(true); setError('');
    try { const user = await login(email, password); onLogin(user); }
    catch (err) { setError(err.message || 'Unable to sign in. Check the API connection.'); }
    finally { setBusy(false); }
  }
  return <main className="auth-shell"><div className="auth-glow"/><motion.section className="auth-card" initial={{opacity:0,y:18}} animate={{opacity:1,y:0}}>
    <div className="auth-brand"><span><Zap size={25} fill="currentColor"/></span><div><b>LIGHTING<span>PANEL</span></b><small>INFRASTRUCTURE CONTROL PLANE</small></div></div>
    <div className="auth-kicker"><i/> SECURE ADMIN ACCESS</div><h1>Welcome back.</h1><p className="auth-copy">Sign in to manage your infrastructure, game servers and nodes.</p>
    <form onSubmit={submit}><label htmlFor="login-email">Email address</label><div className="auth-input"><Mail size={17}/><input id="login-email" type="email" autoComplete="username" placeholder="admin@example.com" value={email} onChange={e=>setEmail(e.target.value)} required/></div><label htmlFor="login-password">Password</label><div className="auth-input"><LockKeyhole size={17}/><input id="login-password" type="password" autoComplete="current-password" placeholder="Enter your password" value={password} onChange={e=>setPassword(e.target.value)} required/></div>
    {error&&<div className="auth-error">{error}</div>}<button className="auth-submit" disabled={busy}>{busy?'Authenticating…':'Sign in to Lighting Panel'} <ArrowRight size={17}/></button></form>
    <div className="auth-security"><ShieldCheck size={15}/> Protected with encrypted password hashing and short-lived access tokens</div>
    <div className="auth-footer"><span><Activity size={13}/> PANEL AUTHENTICATION</span><span>LIGHTING PANEL · 0.3</span></div>
  </motion.section></main>;
}
