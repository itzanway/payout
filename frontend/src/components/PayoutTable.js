import React from 'react';

const STATE = {
  pending:    { bg:'#f1f5f9', color:'#475569' },
  processing: { bg:'#dbeafe', color:'#1d4ed8' },
  completed:  { bg:'#dcfce7', color:'#16a34a' },
  failed:     { bg:'#fee2e2', color:'#dc2626' },
};

const fmt = p => (p/100).toLocaleString('en-IN',{ style:'currency', currency:'INR', maximumFractionDigits:2 });
const fmtD = iso => new Date(iso).toLocaleString('en-IN',{ day:'2-digit', month:'short', hour:'2-digit', minute:'2-digit' });

export default function PayoutTable({ payouts }) {
  if (!payouts.length) return <p style={{ color:'#94a3b8', fontSize:13, textAlign:'center', padding:'20px 0' }}>No payouts yet.</p>;

  const th = { padding:'0 12px 10px 0', fontSize:11, textTransform:'uppercase', letterSpacing:.5, color:'#94a3b8', textAlign:'left', borderBottom:'1px solid #f1f5f9' };
  const td = { padding:'10px 12px 10px 0', fontSize:13, borderBottom:'1px solid #f8fafc' };

  return (
    <div style={{ overflowX:'auto' }}>
      <table style={{ width:'100%', borderCollapse:'collapse' }}>
        <thead>
          <tr>
            {['ID','Amount','Status','Bank Account','Attempts','Created'].map(h => <th key={h} style={th}>{h}</th>)}
          </tr>
        </thead>
        <tbody>
          {payouts.map(p => {
            const s = STATE[p.state] || STATE.pending;
            return (
              <tr key={p.id}>
                <td style={{ ...td, color:'#94a3b8', fontFamily:'monospace' }}>#{p.id}</td>
                <td style={{ ...td, fontWeight:600 }}>{fmt(p.amount_paise)}</td>
                <td style={td}>
                  <span style={{
                    background: s.bg, color: s.color,
                    padding:'2px 10px', borderRadius:20, fontSize:12, fontWeight:500,
                    animation: p.state==='processing' ? 'pulse 2s infinite' : 'none',
                  }}>{p.state}</span>
                </td>
                <td style={{ ...td, color:'#64748b', fontSize:12 }}>{p.bank_account_display}</td>
                <td style={{ ...td, color:'#94a3b8', textAlign:'center' }}>{p.attempt_count}</td>
                <td style={{ ...td, color:'#94a3b8', fontSize:12 }}>{fmtD(p.created_at)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}