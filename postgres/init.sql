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
    created_at TIMESTAMP NOT NULL,
    warehouse_id VARCHAR(255) NOT NULL,
    emp_id VARCHAR(255) NOT NULL,
    zoho_po_number VARCHAR(255),
    scanned_data JSONB
);

CREATE TABLE IF NOT EXISTS validator (
    po_number VARCHAR(255) PRIMARY KEY,
    invoice_status VARCHAR(50),
    invoice_updated_at TIMESTAMP,
    invoice_log VARCHAR(255),
    receipt_status VARCHAR(50),
    receipt_updated_at TIMESTAMP,
    receipt_log VARCHAR(255)
);

CREATE TABLE IF NOT EXISTS decrementor (
    po_number VARCHAR(255) PRIMARY KEY,
    receipt_ids VARCHAR(255)[] NOT NULL,
    original_items JSONB NOT NULL,
    remaining_items JSONB NOT NULL,
    decrement_log VARCHAR(255),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);


