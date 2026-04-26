import React from 'react';

export default function BalanceCard({ label, paise, color, bg }) {
  const rupees = (paise / 100).toLocaleString('en-IN', { style:'currency', currency:'INR', maximumFractionDigits:2 });
  return (
    <div style={{ background: bg, border:`1px solid ${color}33`, borderRadius:12, padding:20 }}>
      <div style={{ fontSize:11, fontWeight:600, textTransform:'uppercase', letterSpacing:1, color, opacity:0.8, marginBottom:6 }}>{label}</div>
      <div style={{ fontSize:24, fontWeight:700, color }}>{rupees}</div>
    </div>
  );
}