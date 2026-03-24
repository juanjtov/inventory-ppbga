export const ROLES = {
  OWNER: 'owner',
  ADMIN: 'admin',
  WORKER: 'worker',
};

export const PAYMENT_METHODS = [
  { value: 'efectivo', label: 'Efectivo' },
  { value: 'datafono', label: 'Datáfono' },
  { value: 'transferencia', label: 'Transferencia' },
  { value: 'fiado', label: 'Por cobrar' },
];

export const SALE_STATUSES = {
  COMPLETED: 'completed',
  PENDING: 'pending',
  VOIDED: 'voided',
};
