import { PoolClient } from 'pg';
import pool from '../db/db';
import { zohoApiService } from './zoho-auth';

interface ReceiptItem {
  name: string;
  quantity: number;
}

interface ReceiptPayload {
  receipt_id: string;
  receipt_number: string;
  po_number: string;
  items: ReceiptItem[];
  warehouse_id: string;
  emp_id: string;
}

// Helper function to manage item quantities
const subtractItems = (original: Map<string, number>, received: ReceiptItem[]) => {
  const remaining = new Map(original);
  for (const item of received) {
    const currentQty = remaining.get(item.name) || 0;
    if (currentQty < item.quantity) {
      throw new Error(`Over-delivery for item "${item.name}". Received ${item.quantity}, but only ${currentQty} were expected.`);
    }
    remaining.set(item.name, currentQty - item.quantity);
  }
  return remaining;
};

export const validateAndProcessReceipt = async (payload: ReceiptPayload) => {
  const client: PoolClient = await pool.connect();

  try {
    await client.query('BEGIN'); // Start transaction

    const { receipt_id, receipt_number, po_number, items, warehouse_id, emp_id } = payload;
    
    // 1. Check validator status
    const validatorRes = await client.query('SELECT receipt_status FROM validator WHERE po_number = $1', [po_number]);
    if (validatorRes.rows.length > 0 && validatorRes.rows[0].receipt_status !== 'pending') {
      throw new Error(`PO ${po_number} is not pending receipt. Current status: ${validatorRes.rows[0].receipt_status}`);
    }
    
    // Insert the receipt record now so it's part of the transaction
    const scanned_data = JSON.stringify({ items });
    await client.query(
      `INSERT INTO receipts (receipt_id, receipt_number, warehouse_id, emp_id, zoho_po_number, scanned_data, created_at)
       VALUES ($1, $2, $3, $4, $5, $6, $7)`,
      [receipt_id, receipt_number, warehouse_id, emp_id, po_number, scanned_data, new Date()]
    );

    // 2. Check decrementor cache
    const decrementorRes = await client.query('SELECT * FROM decrementor WHERE po_number = $1', [po_number]);
    let remainingItemsMap: Map<string, number>;

    if (decrementorRes.rows.length > 0) {
      // Entry exists, decrement from cache
      console.log(`Decrementor cache hit for PO ${po_number}.`);
      const cache = decrementorRes.rows[0];
      const cachedRemainingItems = new Map(
        Object.entries(cache.remaining_items).map(([k, v]) => [k, Number(v)])
      );
      remainingItemsMap = subtractItems(cachedRemainingItems, items);

      // Update decrementor
      const updatedReceiptIds = [...cache.receipt_ids, receipt_id];
      await client.query(
        'UPDATE decrementor SET remaining_items = $1, receipt_ids = $2, updated_at = NOW() WHERE po_number = $3',
        [JSON.stringify(Object.fromEntries(remainingItemsMap)), updatedReceiptIds, po_number]
      );

    } else {
      // No entry, fetch from Zoho for the first time
      console.log(`Decrementor cache miss for PO ${po_number}. Fetching from Zoho.`);
      const poDetails = await zohoApiService.getPurchaseOrderDetailsByNumber(po_number);
      console.log(`Fetched PO details from Zoho:`, poDetails);
      if (!poDetails || !poDetails.line_items) {
        throw new Error(`Could not fetch purchase order details for PO ${po_number} from Zoho.`);
      }

      const originalItemsMap = new Map<string, number>(
        poDetails.line_items.map(item => [item.description.trim(), Number(item.quantity)])
      );
      
      remainingItemsMap = subtractItems(originalItemsMap, items);

      // Create new decrementor entry
      await client.query(
        `INSERT INTO decrementor (po_number, receipt_ids, original_items, remaining_items)
         VALUES ($1, $2, $3, $4)`,
        [po_number, [receipt_id], JSON.stringify(Object.fromEntries(originalItemsMap)), JSON.stringify(Object.fromEntries(remainingItemsMap))]
      );
    }
    
    // 3. Check if PO is fully received and update status
    const isComplete = Array.from(remainingItemsMap.values()).every(qty => qty === 0);
    if (isComplete) {
      console.log(`PO ${po_number} is now fully received. Updating status.`);
      // Update validator
      await client.query(
        `INSERT INTO validator (po_number, receipt_status, receipt_updated_at, receipt_log)
         VALUES ($1, 'matched', NOW(), 'Receipts matched successfully.')
         ON CONFLICT (po_number) DO UPDATE SET
         receipt_status = EXCLUDED.receipt_status,
         receipt_updated_at = EXCLUDED.receipt_updated_at,
         receipt_log = EXCLUDED.receipt_log`,
        [po_number]
      );
      // Clean up cache
      await client.query('DELETE FROM decrementor WHERE po_number = $1', [po_number]);
    } else {
       // If not complete, ensure validator status is 'pending'
       await client.query(
        `INSERT INTO validator (po_number, receipt_status, receipt_updated_at, receipt_log)
         VALUES ($1, 'pending', NOW(), 'Partial receipt received.')
         ON CONFLICT (po_number) DO UPDATE SET
         receipt_status = EXCLUDED.receipt_status,
         receipt_updated_at = EXCLUDED.receipt_updated_at,
         receipt_log = EXCLUDED.receipt_log`,
        [po_number]
      );
    }

    await client.query('COMMIT'); // Commit transaction
    return { success: true, message: 'Receipt processed successfully.', status: isComplete ? 'matched' : 'pending' };

  } catch (error: any) {
    await client.query('ROLLBACK'); // Rollback on error
    console.error('Error during receipt validation:', error.message);
    throw error; // Re-throw to be caught by the API controller
  } finally {
    client.release(); // Release client back to the pool
  }
};