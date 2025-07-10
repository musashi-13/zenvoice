type Invoice = {
  invoice_id: string
  message_id: string
  sender: string
  subject: string
  created_at: string
  updated_at: string
  s3_url: string
  scanned_data: string // raw JSON string
}
