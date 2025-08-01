// src/routes/api-routes.ts
import express from 'express';
import { getAllInvoices } from '../api/invoice-store';
import { generatePresignedDownloadUrl } from '../api/s3';
import { addReceipts, getAllReceipts } from '../api/receipt-store';

const router = express.Router();

router.get('/invoices', getAllInvoices); // /api/invoices
router.get('/s3/fetch', generatePresignedDownloadUrl); // /api/s3/fetch/:s3_url
router.post('/receipts/add', addReceipts); // /api/s3/fetch with body
router.get('/receipts', getAllReceipts);
export default router;
