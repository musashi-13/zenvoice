import { createFileRoute } from '@tanstack/react-router'
import { useState } from 'react'

export const Route = createFileRoute('/warehouse/receipt/add')({
  component: RouteComponent,
})

interface Item {
  name: string;
  quantity: number;
}

interface WarehouseReceipt {
  receipt_number: string;
  PO_number: string;
  items: Item[];
}

function RouteComponent() {
  const [receiptNumber, setReceiptNumber] = useState('')
  const [poNumber, setPoNumber] = useState('')
  const [items, setItems] = useState<Item[]>([{ name: '', quantity: 0 }])
  const [savedData, setSavedData] = useState<WarehouseReceipt | null>(null)

  const addItem = () => {
    setItems([...items, { name: '', quantity: 0 }])
  }

  const removeItem = (index: number) => {
    if (items.length > 1) {
      setItems(items.filter((_, i) => i !== index))
    }
  }

  const updateItem = (index: number, field: keyof Item, value: string | number) => {
    const updatedItems = items.map((item, i) => 
      i === index ? { ...item, [field]: value } : item
    )
    setItems(updatedItems)
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    
    if (!receiptNumber.trim() || !poNumber.trim()) {
      alert('Please fill in receipt number and PO number')
      return
    }

    const validItems = items.filter(item => item.name.trim() && item.quantity > 0)
    if (validItems.length === 0) {
      alert('Please add at least one item with name and quantity')
      return
    }

    const warehouseData: WarehouseReceipt = {
      receipt_number: receiptNumber,
      PO_number: poNumber,
      items: validItems
    }

    setSavedData(warehouseData)
    console.log('Warehouse Receipt Data:', JSON.stringify(warehouseData, null, 2))
  }

  const resetForm = () => {
    setReceiptNumber('')
    setPoNumber('')
    setItems([{ name: '', quantity: 0 }])
    setSavedData(null)
  }

  return (
    <div className="min-h-screen bg-neutral-900 text-white p-8">
      <div className="max-w-4xl mx-auto">
        <h1 className="text-4xl font-bold text-center text-white mb-8">
          Warehouse Receipt Form
        </h1>
        
        <form onSubmit={handleSubmit} className="bg-neutral-900 p-8 rounded-lg shadow-xl border border-gray-700">
          <div className="mb-6">
            <label htmlFor="receiptNumber" className="block text-sm font-medium text-gray-300 mb-2">
              Receipt Number:
            </label>
            <input
              type="text"
              id="receiptNumber"
              value={receiptNumber}
              onChange={(e) => setReceiptNumber(e.target.value)}
              placeholder="Enter receipt number"
              className="w-full px-4 py-3 bg-gray-700 border border-gray-600 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              required
            />
          </div>

          <div className="mb-6">
            <label htmlFor="poNumber" className="block text-sm font-medium text-gray-300 mb-2">
              Purchase Order Number:
            </label>
            <input
              type="text"
              id="poNumber"
              value={poNumber}
              onChange={(e) => setPoNumber(e.target.value)}
              placeholder="Enter PO number"
              className="w-full px-4 py-3 bg-gray-700 border border-gray-600 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              required
            />
          </div>

          <div className="mb-8">
            <h3 className="text-xl font-semibold text-gray-200 mb-4">Items</h3>
            <div className="space-y-3">
              {items.map((item, index) => (
                <div key={index} className="flex flex-col sm:flex-row gap-3 items-start sm:items-center">
                  <input
                    type="text"
                    placeholder="Item name"
                    value={item.name}
                    onChange={(e) => updateItem(index, 'name', e.target.value)}
                    className="flex-1 px-4 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  />
                  <input
                    type="number"
                    placeholder="Quantity"
                    min="1"
                    value={item.quantity || ''}
                    onChange={(e) => updateItem(index, 'quantity', parseInt(e.target.value) || 0)}
                    className="w-full sm:w-32 px-4 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  />
                  <button
                    type="button"
                    onClick={() => removeItem(index)}
                    disabled={items.length === 1}
                    className="px-4 py-2 bg-red-600 hover:bg-red-700 disabled:bg-gray-600 disabled:cursor-not-allowed text-white rounded-lg font-medium transition-colors duration-200"
                  >
                    Remove
                  </button>
                </div>
              ))}
            </div>
            
            <button 
              type="button" 
              onClick={addItem} 
              className="mt-4 px-6 py-2 bg-green-600 hover:bg-green-700 text-white rounded-lg font-medium transition-colors duration-200"
            >
              Add Another Item
            </button>
          </div>

          <div className="flex flex-col sm:flex-row gap-4">
            <button 
              type="submit" 
              className="flex-1 px-6 py-3 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium transition-colors duration-200"
            >
              Save Receipt
            </button>
            <button 
              type="button" 
              onClick={resetForm} 
              className="flex-1 px-6 py-3 bg-red-600 hover:bg-red-700 text-white rounded-lg font-medium transition-colors duration-200"
            >
              Reset Form
            </button>
          </div>
        </form>

        {savedData && (
          <div className="mt-8 p-6 bg-green-900 border border-green-700 rounded-lg">
            <h3 className="text-xl font-semibold text-green-300 mb-4">
              Saved Receipt Data (JSON):
            </h3>
            <pre className="bg-gray-800 p-4 rounded-lg border border-gray-700 overflow-x-auto text-sm text-gray-300 font-mono">
              {JSON.stringify(savedData, null, 2)}
            </pre>
          </div>
        )}
      </div>
    </div>
  )
}