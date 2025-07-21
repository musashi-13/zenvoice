CREATE TABLE IF NOT EXISTS invoice_store (
    invoice_id UUID PRIMARY KEY,
    message_id VARCHAR(255) NOT NULL UNIQUE,
    sender VARCHAR(255) NOT NULL,
    subject TEXT,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL,
    s3_url TEXT NOT NULL,
    zoho_po_number VARCHAR(255),
    zoho_bill_number VARCHAR(255),
    scanned_data JSONB
);

CREATE TABLE IF NOT EXISTS receipts (
    receipt_id UUID PRIMARY KEY,
    receipt_number VARCHAR(255) NOT NULL,
    warehouse_id VARCHAR(255) NOT NULL,
    emp_id VARCHAR(255) NOT NULL,
    zoho_po_number VARCHAR(255),
    scanned_data JSONB
);