import React, { useState, useEffect, useCallback } from 'react';
import { getMerchant, getLedger, getPayouts, createPayout } from '../api/client';
import BalanceCard  from '../components/BalanceCard';
import PayoutForm   from '../components/PayoutForm';
import PayoutTable  from '../components/PayoutTable';
import LedgerTable  from '../components/LedgerTable';

export default function Dashboard({ merchant: init, onMerchantUpdate }) {
  const [merchant, setMerchant] = useState(init);
  const [ledger,   setLedger]   = useState([]);
  const [payouts,  setPayouts]  = useState([]);
  const [tab,      setTab]      = useState('payouts');
  const [err,      setErr]      = useState(null);
  const [ok,       setOk]       = useState(null);
  const [busy,     setBusy]     = useState(false);

  const refresh = useCallback(async () => {
    const [mR, lR, pR] = await Promise.all([
      getMerchant(init.id), getLedger(init.id), getPayouts(init.id),
    ]);
    setMerchant(mR.data);
    setLedger(lR.data);
    setPayouts(pR.data);
    onMerchantUpdate(mR.data);
  }, [init.id, onMerchantUpdate]);

  useEffect(() => {
    refresh();
    const iv = setInterval(refresh, 3000);
    return () => clearInterval(iv);
  }, [refresh]);

  const handlePayout = async ({ amountRupees, bankAccountId, idempotencyKey }) => {
    setErr(null); setOk(null); setBusy(true);
    const paise = Math.round(parseFloat(amountRupees) * 100);
    try {
      const r = await createPayout(merchant.id, paise, bankAccountId, idempotencyKey);
      setOk(`✓ Payout #${r.data.id} queued — ₹${(paise/100).toFixed(2)} processing`);
      refresh();
    } catch (e) {
      setErr(e.response?.data?.error || 'Unknown error');
    } finally {
      setBusy(false);
    }
  };

  const card = { background:'#fff', border:'1px solid #e2e8f0', borderRadius:12, padding:24, marginBottom:0 };

  return (
    <main style={{ maxWidth:900, margin:'0 auto', padding:'32px 16px' }}>

      {/* Balance row */}
      <div style={{ display:'grid', gridTemplateColumns:'repeat(3,1fr)', gap:16, marginBottom:24 }}>
        <BalanceCard label="Available"    paise={merchant.available_balance_paise} color="#4f46e5" bg="#eef2ff" />
        <BalanceCard label="Held"         paise={merchant.held_balance_paise}      color="#d97706" bg="#fffbeb" />
        <BalanceCard label="Total In"     paise={merchant.total_credited_paise}    color="#16a34a" bg="#f0fdf4" />
      </div>

      {/* Payout form */}
      <div style={{ ...card, marginBottom:24 }}>
        <h2 style={{ margin:'0 0 16px', fontSize:15, fontWeight:600 }}>Request Payout</h2>
        {err && <div style={{ background:'#fef2f2', border:'1px solid #fecaca', color:'#dc2626', borderRadius:8, padding:'8px 14px', marginBottom:12, fontSize:13 }}>{err}</div>}
        {ok  && <div style={{ background:'#f0fdf4', border:'1px solid #bbf7d0', color:'#16a34a', borderRadius:8, padding:'8px 14px', marginBottom:12, fontSize:13 }}>{ok}</div>}
        <PayoutForm
          bankAccounts={merchant.bank_accounts}
          availablePaise={merchant.available_balance_paise}
          submitting={busy}
          onSubmit={handlePayout}
        />
      </div>

      {/* Tabs */}
      <div style={card}>
        <div style={{ borderBottom:'1px solid #e2e8f0', marginBottom:16, display:'flex', gap:0 }}>
          {['payouts','ledger'].map(t => (
            <button key={t} onClick={() => setTab(t)} style={{
              padding:'10px 20px', border:'none', background:'none', cursor:'pointer', fontSize:13,
              fontWeight: tab===t ? 600 : 400,
              color: tab===t ? '#4f46e5' : '#64748b',
              borderBottom: tab===t ? '2px solid #4f46e5' : '2px solid transparent',
            }}>
              {t === 'payouts' ? 'Payout History' : 'Ledger Entries'}
            </button>
          ))}
        </div>
        {tab === 'payouts' ? <PayoutTable payouts={payouts} /> : <LedgerTable entries={ledger} />}
      </div>
    </main>
  );
}