import axios from 'axios';

const BASE = process.env.REACT_APP_API_URL || '/api/v1';
const api  = axios.create({ baseURL: BASE });

export const getMerchants  = ()                                              => api.get('/merchants/');
export const getMerchant   = (id)                                            => api.get(`/merchants/${id}/`);
export const getLedger     = (merchantId)                                    => api.get(`/merchants/${merchantId}/ledger/`);
export const getPayouts    = (merchantId)                                    => api.get(`/payouts/list/?merchant_id=${merchantId}`);
export const createPayout  = (merchantId, amountPaise, bankAccountId, key)  =>
  api.post('/payouts/',
    { amount_paise: amountPaise, bank_account_id: bankAccountId },
    { headers: { 'Idempotency-Key': key, 'X-Merchant-Id': String(merchantId) } }
  );