import { createFileRoute } from '@tanstack/react-router'
import { useEffect, useState } from 'react'
import {
  useReactTable,
  getCoreRowModel,
  getExpandedRowModel,
  flexRender,
  type ColumnDef,
} from '@tanstack/react-table'
import { Button } from '@/components/ui/button'

import { ChevronDown, ChevronRight, Download } from 'lucide-react'

export const Route = createFileRoute('/invoices')({
  component: RouteComponent,
})

type Invoice = {
  invoice_id: string
  message_id: string
  sender: string
  subject: string
  created_at: string
  updated_at: string
  s3_url: string
  scanned_data: string
}

function RouteComponent() {
  const [data, setData] = useState<Invoice[]>([])
  const [page, setPage] = useState(1)
  const [totalPages, setTotalPages] = useState(1)
  const [loading, setLoading] = useState(false)
  const [expanded, setExpanded] = useState<Record<string, boolean>>({})

  const fetchData = async (page: number) => {
    setLoading(true)
    try {
      const res = await fetch(`http://localhost:4000/api/invoices?page=${page}&limit=10`)
      const json = await res.json()
      setData(json.data)
      setTotalPages(json.pagination.totalPages)
    } catch (err) {
      console.error('Failed to fetch invoices', err)
    } finally {
      setLoading(false)
    }
  }

  const fetchPresignedUrl = async (s3_url: string) => {
  try {
    const res = await fetch(`http://localhost:4000/api/s3/fetch?s3_url=${encodeURIComponent(s3_url)}`);
    const json = await res.json();
    window.open(json.presignedUrl, '_blank');
  } catch (err) {
    console.error('Failed to fetch presigned URL', err);
  }
};

  useEffect(() => {
    fetchData(page)
  }, [page])

  const columns: ColumnDef<Invoice>[] = [
    {
      id: 'expander',
      header: '',
      cell: ({ row }) => (
        <Button
          variant="ghost"
          size="icon"
          onClick={() => {
            const id = row.original.invoice_id
            setExpanded(prev => ({ ...prev, [id]: !prev[id] }))
          }}
        >
          {expanded[row.original.invoice_id] ? (
            <ChevronDown className="h-4 w-4" />
          ) : (
            <ChevronRight className="h-4 w-4" />
          )}
        </Button>
      ),
    },
    {
      header: 'Invoice ID',
      accessorKey: 'invoice_id',
    },
    {
      header: 'Sender',
      accessorKey: 'sender',
    },
    {
      header: 'Subject',
      accessorKey: 'subject',
    },
    {
      header: 'Created At',
      accessorKey: 'created_at',
      cell: info => new Date(info.getValue<string>()).toLocaleString(),
    },
    {
      header: 'Updated At',
      accessorKey: 'updated_at',
      cell: info => new Date(info.getValue<string>()).toLocaleString(),
    },
    {
      header: 'PDF',
      accessorKey: 's3_url',
      cell: ({ row }) => (
        <Button
          onClick={() => fetchPresignedUrl(row.original.s3_url)}
          variant="secondary"
          size="sm"
          className='cursor-pointer'
        >
          <Download className="w-4 h-4 mr-1" />
          Download
        </Button>
      ),
    },
  ]

  const table = useReactTable({
      data,
      columns,
      getCoreRowModel: getCoreRowModel(),
      getExpandedRowModel: getExpandedRowModel(),
      state: {
          expanded,
      },
      filterFns: {
        fuzzy: () => true, // Replace with actual fuzzy filter logic if needed
      },
  })

  return (
    <div className="p-4 m-4 overflow-x-auto">
      <h1 className="text-xl font-semibold mb-4">Invoices</h1>
      {loading ? (
        <p>Loading...</p>
      ) : (
        <>
          <table className="w-full border-collapse text-left text-sm">
            <thead>
              {table.getHeaderGroups().map(headerGroup => (
                <tr key={headerGroup.id}>
                  {headerGroup.headers.map(header => (
                    <th key={header.id} className="border-b p-2 font-medium">
                      {flexRender(header.column.columnDef.header, header.getContext())}
                    </th>
                  ))}
                </tr>
              ))}
            </thead>
            <tbody>
              {table.getRowModel().rows.map(row => (
                <>
                  <tr key={row.id}>
                    {row.getVisibleCells().map(cell => (
                      <td key={cell.id} className="border-b p-2 align-top">
                        {flexRender(cell.column.columnDef.cell, cell.getContext())}
                      </td>
                    ))}
                  </tr>
                  {expanded[row.original.invoice_id] && (
                    <tr>
                      <td colSpan={columns.length} className="bg-zinc-50 p-4 text-sm">
                        {(() => {
                          try {
                            const parsed = JSON.parse(row.original.scanned_data)
                            return (
                              <>
                                <div className="mb-2">
                                  <span className="font-medium">Vendor:</span>{' '}
                                  {parsed.vendor_name || 'N/A'}
                                </div>
                                <div className="mb-2">
                                  <span className="font-medium">Total:</span> ₹
                                  {parsed.total?.toLocaleString('en-IN') || '0'}
                                </div>
                                <pre className="bg-zinc-100 p-4 text-xs rounded overflow-auto max-h-96">
                                  {JSON.stringify(parsed, null, 2)}
                                </pre>
                              </>
                            )
                          } catch {
                            return <div className="text-red-500">Invalid JSON</div>
                          }
                        })()}
                      </td>
                    </tr>
                  )}
                </>
              ))}
            </tbody>
          </table>

          <div className="flex justify-between items-center mt-4">
            <Button disabled={page <= 1} onClick={() => setPage(p => p - 1)}>
              Previous
            </Button>
            <span>
              Page {page} of {totalPages}
            </span>
            <Button disabled={page >= totalPages} onClick={() => setPage(p => p + 1)}>
              Next
            </Button>
          </div>
        </>
      )}
    </div>
  )
}
