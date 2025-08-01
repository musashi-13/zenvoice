// src/api/receipt-store.ts
import { Request, Response } from 'express';
import { v4 as uuidv4 } from 'uuid';
import pool from '../db/db';
import { validateAndProcessReceipt } from '../services/receipt-validator';

export const getAllReceipts = async (req: Request, res: Response) => {
    const page = parseInt(req.query.page as string, 10) || 1;
    const limit = parseInt(req.query.limit as string, 10) || 10;
    const offset = (page - 1) * limit;

    try {
        const totalResult = await pool.query('SELECT COUNT(*) FROM receipts');
        const totalCount = parseInt(totalResult.rows[0].count, 10);
        const totalPages = Math.ceil(totalCount / limit);

        const receiptsQuery = `
            SELECT receipt_id, receipt_number, warehouse_id, emp_id, zoho_po_number, scanned_data, created_at
            FROM receipts
            ORDER BY created_at DESC
            LIMIT $1
            OFFSET $2;
        `;
        const receiptsResult = await pool.query(receiptsQuery, [limit, offset]);

        res.status(200).json({
            data: receiptsResult.rows,
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
        console.error('Error fetching receipts:', error);
        res.status(500).json({ error: 'Failed to fetch receipts' });
    }
};

export const addReceipts = async (req: Request, res: Response) => {
    const { receipt_number, po_number, items, warehouse_id, emp_id } = req.body;

    if (!receipt_number || !po_number || !items || !Array.isArray(items)) {
        return res.status(400).json({ error: 'Missing or invalid receipt data' });
    }

    try {
        const receipt_id = uuidv4();
        
        // Call the validator service which handles the entire logic
        const result = await validateAndProcessReceipt({
            receipt_id,
            receipt_number,
            po_number,
            items,
            warehouse_id,
            emp_id,
        });

        res.status(201).json({
            message: result.message,
            receipt_id: receipt_id,
            po_number: po_number,
            validation_status: result.status
        });

    } catch (error: any) {
        console.error('Error adding receipt:', error.message);
        // Provide specific feedback if it's a validation error
        res.status(400).json({ error: error.message || 'Failed to process receipt' });
    }
};