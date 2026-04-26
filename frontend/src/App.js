import React, { useState, useEffect } from 'react';
import { getMerchants } from './api/client';
import Dashboard from './pages/Dashboard';

export default function App() {
  const [merchants, setMerchants]   = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [loading, setLoading]       = useState(true);
  const [error, setError]           = useState(null);

  useEffect(() => {
    getMerchants()
      .then(r => { setMerchants(r.data); if (r.data.length) setSelectedId(r.data[0].id); })
      .catch(() => setError('Cannot reach API — is Django running on :8000?'))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return (
    <div style={{ display:'flex', justifyContent:'center', alignItems:'center', minHeight:'100vh' }}>
      <p style={{ color:'#64748b', fontSize:18 }}>Loading…</p>
    </div>
  );

  if (error) return (
    <div style={{ display:'flex', justifyContent:'center', alignItems:'center', minHeight:'100vh' }}>
      <div style={{ background:'#fef2f2', border:'1px solid #fecaca', color:'#dc2626', padding:'24px 32px', borderRadius:12, textAlign:'center' }}>
        <strong>Connection Error</strong><br/><span style={{ fontSize:14 }}>{error}</span>
      </div>
    </div>
  );

  const selected = merchants.find(m => m.id === selectedId);

  return (
    <div style={{ minHeight:'100vh', background:'#f8fafc' }}>
      <header style={{ background:'#fff', borderBottom:'1px solid #e2e8f0', padding:'12px 24px', display:'flex', alignItems:'center', gap:16 }}>
        <div style={{ display:'flex', alignItems:'center', gap:8 }}>
          <div style={{ width:28, height:28, borderRadius:8, background:'#4f46e5', display:'flex', alignItems:'center', justifyContent:'center' }}>
            <span style={{ color:'#fff', fontWeight:700, fontSize:13 }}>P</span>
          </div>
          <span style={{ fontWeight:600, color:'#1e293b' }}>Playto Pay</span>
          <span style={{ color:'#94a3b8', fontSize:12 }}>Payout Engine</span>
        </div>
        <div style={{ marginLeft:'auto', display:'flex', alignItems:'center', gap:8 }}>
          <label style={{ fontSize:13, color:'#64748b' }}>Merchant:</label>
          <select
            value={selectedId || ''}
            onChange={e => setSelectedId(Number(e.target.value))}
            style={{ border:'1px solid #e2e8f0', borderRadius:8, padding:'6px 12px', fontSize:13, background:'#fff' }}
          >
            {merchants.map(m => <option key={m.id} value={m.id}>{m.name}</option>)}
          </select>
        </div>
      </header>
      {selected && (
        <Dashboard
          key={selectedId}
          merchant={selected}
          onMerchantUpdate={updated => setMerchants(prev => prev.map(m => m.id === updated.id ? updated : m))}
        />
      )}
    </div>
  );
}