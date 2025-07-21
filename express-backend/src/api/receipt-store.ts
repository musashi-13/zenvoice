// src/api/receipt-store.ts
import { Request, Response } from 'express';
import { v4 as uuidv4 } from 'uuid';
import pool from '../db/db'; // Import the shared pool

export const addReceipts = async (req: Request, res: Response) => {
  const { receipt_number, PO_number, items } = req.body;

  if (!receipt_number || !PO_number || !items || !Array.isArray(items)) {
    return res.status(400).json({ error: 'Missing or invalid receipt data' });
  }

  try {
    const receiptId = uuidv4();
    const warehouseId = 'WH001'; // Dummy value
    const empId = 'EMP001'; // Dummy value
    const scannedData = JSON.stringify({ items }); // Store items as JSON in scanned_data

    const query = `
      INSERT INTO receipts (receipt_id, receipt_number, warehouse_id, emp_id, zoho_po_number, scanned_data)
      VALUES ($1, $2, $3, $4, $5, $6)
      RETURNING receipt_id, receipt_number, warehouse_id, emp_id, zoho_po_number, scanned_data;
    `;
    const values = [receiptId, receipt_number, warehouseId, empId, PO_number, scannedData];

    const result = await pool.query(query, values);
    const newReceipt = result.rows[0];

    res.status(201).json({
      message: 'Receipt added successfully',
      receipt: newReceipt,
    });
  } catch (error) {
    console.error('Error adding receipt:', error);
    res.status(500).json({ error: 'Failed to add receipt' });
  }
};