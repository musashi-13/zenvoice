// src/routes/api-routes.ts
import express from 'express';
import { getAllInvoices } from '../api/invoice-store';

const router = express.Router();

router.get('/invoices', getAllInvoices); // /api/invoices

export default router;
