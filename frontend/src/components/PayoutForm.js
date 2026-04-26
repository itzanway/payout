import React, { useState } from 'react';

function uuid() {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, c => {
    const r = Math.random()*16|0;
    return (c==='x' ? r : (r&0x3|0x8)).toString(16);
  });
}

const inp = {
  border:'1px solid #e2e8f0', borderRadius:8, padding:'8px 12px',
  fontSize:13, width:'100%', outline:'none',
};

export default function PayoutForm({ bankAccounts, availablePaise, onSubmit, submitting }) {
  const [amount,  setAmount]  = useState('');
  const [bankId,  setBankId]  = useState(bankAccounts[0]?.id || '');
  const [iKey,    setIKey]    = useState(uuid());

  const maxRupees = availablePaise / 100;

  const submit = e => {
    e.preventDefault();
    onSubmit({ amountRupees: amount, bankAccountId: bankId, idempotencyKey: iKey });
    setIKey(uuid());
  };

  return (
    <form onSubmit={submit} style={{ display:'flex', gap:12, flexWrap:'wrap', alignItems:'flex-end' }}>
      <div style={{ flex:'1 1 140px' }}>
        <div style={{ fontSize:11, color:'#64748b', marginBottom:4 }}>Amount (₹)</div>
        <input style={inp} type="number" min="1" max={maxRupees} step="0.01"
          placeholder="e.g. 5000" value={amount} onChange={e => setAmount(e.target.value)} required />
        <div style={{ fontSize:11, color:'#94a3b8', marginTop:2 }}>Max ₹{maxRupees.toFixed(2)}</div>
      </div>

      <div style={{ flex:'1 1 200px' }}>
        <div style={{ fontSize:11, color:'#64748b', marginBottom:4 }}>Bank Account</div>
        <select style={{ ...inp, background:'#fff' }} value={bankId} onChange={e => setBankId(e.target.value)}>
          {bankAccounts.map(ba => (
            <option key={ba.id} value={ba.id}>
              {ba.account_holder_name} ···{ba.account_number.slice(-4)} ({ba.ifsc_code})
            </option>
          ))}
        </select>
      </div>

      <div style={{ flex:'2 1 260px' }}>
        <div style={{ fontSize:11, color:'#64748b', marginBottom:4 }}>Idempotency Key</div>
        <div style={{ display:'flex', gap:4 }}>
          <input style={{ ...inp, fontFamily:'monospace', fontSize:11 }}
            value={iKey} onChange={e => setIKey(e.target.value)} />
          <button type="button" onClick={() => setIKey(uuid())}
            style={{ border:'1px solid #e2e8f0', borderRadius:8, padding:'0 10px', background:'#f8fafc', cursor:'pointer', fontSize:16 }}>↺</button>
        </div>
      </div>

      <button type="submit" disabled={submitting || !amount || availablePaise <= 0}
        style={{
          padding:'9px 20px', background: submitting ? '#818cf8' : '#4f46e5',
          color:'#fff', border:'none', borderRadius:8, fontWeight:600,
          fontSize:13, cursor: submitting ? 'not-allowed' : 'pointer', whiteSpace:'nowrap',
        }}>
        {submitting ? 'Submitting…' : 'Request Payout'}
      </button>
    </form>
  );
}