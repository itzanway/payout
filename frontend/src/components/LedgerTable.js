import React from 'react';

const TYPE = {
  CREDIT:        { label:'Credit',  bg:'#dcfce7', color:'#16a34a' },
  DEBIT_HOLD:    { label:'Hold',    bg:'#fef9c3', color:'#d97706' },
  DEBIT_RELEASE: { label:'Release', bg:'#dbeafe', color:'#1d4ed8' },
  DEBIT_SETTLE:  { label:'Settled', bg:'#f1f5f9', color:'#475569' },
};

const fmt = p => {
  const abs = Math.abs(p)/100;
  const s = abs.toLocaleString('en-IN',{ style:'currency', currency:'INR', maximumFractionDigits:2 });
  return p >= 0 ? `+${s}` : `−${s}`;
};
const fmtD = iso => new Date(iso).toLocaleString('en-IN',{ day:'2-digit', month:'short', hour:'2-digit', minute:'2-digit' });

export default function LedgerTable({ entries }) {
  if (!entries.length) return <p style={{ color:'#94a3b8', fontSize:13, textAlign:'center', padding:'20px 0' }}>No entries.</p>;

  const th = { padding:'0 12px 10px 0', fontSize:11, textTransform:'uppercase', letterSpacing:.5, color:'#94a3b8', textAlign:'left', borderBottom:'1px solid #f1f5f9' };
  const td = { padding:'10px 12px 10px 0', fontSize:13, borderBottom:'1px solid #f8fafc' };

  return (
    <div style={{ overflowX:'auto' }}>
      <table style={{ width:'100%', borderCollapse:'collapse' }}>
        <thead>
          <tr>{['Type','Amount','Description','Date'].map(h => <th key={h} style={th}>{h}</th>)}</tr>
        </thead>
        <tbody>
          {entries.map(e => {
            const t = TYPE[e.entry_type] || { label: e.entry_type, bg:'#f1f5f9', color:'#475569' };
            return (
              <tr key={e.id}>
                <td style={td}>
                  <span style={{ background:t.bg, color:t.color, padding:'2px 10px', borderRadius:20, fontSize:12, fontWeight:500 }}>{t.label}</span>
                </td>
                <td style={{ ...td, fontFamily:'monospace', fontWeight:600, color: e.amount_paise>=0 ? '#16a34a' : '#dc2626', fontSize:12 }}>
                  {fmt(e.amount_paise)}
                </td>
                <td style={{ ...td, color:'#64748b', fontSize:12 }}>{e.description}</td>
                <td style={{ ...td, color:'#94a3b8', fontSize:12 }}>{fmtD(e.created_at)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}