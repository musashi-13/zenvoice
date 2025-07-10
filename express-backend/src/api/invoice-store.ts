// src/api/invoiceStoreApi.ts
import { Request, Response } from 'express';
import pool from '../db/db';

export const getAllInvoices = async (req: Request, res: Response) => {
  const page = parseInt(req.query.page as string) || 1;
  const limit = parseInt(req.query.limit as string) || 10;
  const offset = (page - 1) * limit;

  try {
    const countResult = await pool.query('SELECT COUNT(*) FROM invoice_store');
    const totalCount = parseInt(countResult.rows[0].count, 10);
    const totalPages = Math.ceil(totalCount / limit);

    const result = await pool.query(
      `
      SELECT 
        invoice_id,
        message_id,
        sender,
        subject,
        created_at,
        updated_at,
        s3_url,
        zoho_po_number,
        zoho_bill_number,
        scanned_data
      FROM invoice_store
      ORDER BY created_at DESC
      LIMIT $1 OFFSET $2
      `,
      [limit, offset]
    );

    res.json({
      data: result.rows,
      pagination: {
        page,
        limit,
        totalCount,
        totalPages,
        hasNextPage: page < totalPages,
        hasPreviousPage: page > 1,
      },
    });
  } catch (error) {
    console.error('Error fetching invoices:', error);
    res.status(500).json({ error: 'Internal server error' });
  }
};
