import { Request, Response } from 'express';
import pool from '../db/db';

export const getValidatorStatus = async (req: Request, res: Response) => {
  const page = parseInt(req.query.page as string) || 1;
  const limit = parseInt(req.query.limit as string) || 10;
  const offset = (page - 1) * limit;

  try {
    // Get total count for pagination
    const countResult = await pool.query('SELECT COUNT(*) FROM validator');
    const totalCount = parseInt(countResult.rows[0].count, 10);
    const totalPages = Math.ceil(totalCount / limit);

    // Fetch the paginated data
    const result = await pool.query(
      `
      SELECT 
        po_number,
        invoice_status,
        invoice_updated_at,
        invoice_log,
        receipt_status,
        receipt_updated_at,
        receipt_log
      FROM validator
      ORDER BY receipt_updated_at DESC, invoice_updated_at DESC
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
    console.error('Error fetching validator status:', error);
    res.status(500).json({ error: 'Internal server error' });
  }
};