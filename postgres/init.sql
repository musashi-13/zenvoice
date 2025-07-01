CREATE TABLE IF NOT EXISTS invoice_store (
    invoice_id UUID PRIMARY KEY,
    message_id VARCHAR(255) NOT NULL,
    sender VARCHAR(255) NOT NULL,
    subject TEXT,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL,
    s3_url TEXT NOT NULL,
    zoho_po_number VARCHAR(255),
    zoho_bill_number VARCHAR(255),
    scanned_data JSONB
);