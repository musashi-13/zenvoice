// src/routes/warehouse/receipts.tsx
import { createFileRoute } from '@tanstack/react-router';
import { useEffect, useState } from 'react';
import {
  useReactTable,
  getCoreRowModel,
  getExpandedRowModel,
  flexRender,
  type ColumnDef,
} from '@tanstack/react-table';
import { Button } from '@/components/ui/button';
import { ChevronDown, ChevronRight } from 'lucide-react';
import { Badge } from '@/components/ui/badge';

export const Route = createFileRoute('/warehouse/receipts')({
  component: RouteComponent,
});

type ScannedData = {
  items: Array<{ name: string; quantity: number }>;
};

type Receipt = {
  receipt_id: string;
  receipt_number: string;
  warehouse_id: string;
  emp_id: string;
  zoho_po_number: string;
  scanned_data: ScannedData;
  created_at: string;
};

function RouteComponent() {
  const [data, setData] = useState<Receipt[]>([]);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [loading, setLoading] = useState(false);
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});

  const fetchData = async (page: number) => {
    setLoading(true);
    try {
      const res = await fetch(`http://localhost:4000/api/receipts?page=${page}&limit=10`);
      const json = await res.json();
      
      // Since the data is already parsed, we can just set it
      setData(json.data);
      setTotalPages(json.pagination.totalPages);
    } catch (err) {
      console.error('Failed to fetch receipts', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData(page);
  }, [page]);

  const columns: ColumnDef<Receipt>[] = [
    
    {
      header: 'Receipt ID',
      accessorKey: 'receipt_id',
    },
    {
      header: 'Receipt Number',
      accessorKey: 'receipt_number',
    },
    {
      header: 'Warehouse ID',
      accessorKey: 'warehouse_id',
    },
    {
      header: 'Employee ID',
      accessorKey: 'emp_id',
    },
    {
      header: 'ZOHO PO Number',
      accessorKey: 'zoho_po_number',
    },
    {
      header: 'Created At',
      accessorKey: 'created_at',
      cell: (info) => new Date(info.getValue<string>()).toLocaleString(),
    },
    {
      id: 'expander',
      header: '',
      cell: ({ row }) => (
        <Button
          variant="ghost"
          size="icon"
          onClick={() => {
            const id = row.original.receipt_id;
            setExpanded((prev) => ({ ...prev, [id]: !prev[id] }));
          }}
        >
          {expanded[row.original.receipt_id] ? (
            <ChevronDown className="h-4 w-4" />
          ) : (
            <ChevronRight className="h-4 w-4" />
          )}
        </Button>
      ),
    },
  ];

  const table = useReactTable({
      data,
      columns,
      getCoreRowModel: getCoreRowModel(),
      getExpandedRowModel: getExpandedRowModel(),
      state: {
          expanded,
      },
      filterFns: {
        fuzzy: () => true,
      }
  });

  return (
    <div className="p-4 m-4 overflow-x-auto">
      <h1 className="text-xl font-semibold mb-4">Receipts</h1>
      {loading ? (
        <p>Loading...</p>
      ) : (
        <>
          <div className="rounded-md border">
            <table className="w-full caption-bottom text-sm">
              <thead className="[&_tr]:border-b">
                {table.getHeaderGroups().map((headerGroup) => (
                  <tr key={headerGroup.id} className="border-b transition-colors hover:bg-muted/50 data-[state=selected]:bg-muted">
                    {headerGroup.headers.map((header) => (
                      <th key={header.id} className="h-12 px-4 text-left align-middle font-medium text-muted-foreground [&:has([role=checkbox])]:pr-0">
                        {flexRender(header.column.columnDef.header, header.getContext())}
                      </th>
                    ))}
                  </tr>
                ))}
              </thead>
              <tbody className="[&_tr:last-child]:border-0">
                {table.getRowModel().rows.map((row) => (
                  <>
                    <tr key={row.id} className="border-b transition-colors items-center hover:bg-muted/50 data-[state=selected]:bg-muted">
                      {row.getVisibleCells().map((cell) => (
                        <td key={cell.id} className="p-4 align-top [&:has([role=checkbox])]:pr-0">
                          {flexRender(cell.column.columnDef.cell, cell.getContext())}
                        </td>
                      ))}
                    </tr>
                    {expanded[row.original.receipt_id] && (
                      <tr>
                        <td colSpan={columns.length} className="bg-zinc-50 p-4 text-sm">
                          <h4 className="font-semibold mb-2">Scanned Items:</h4>
                          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                            {row.original.scanned_data?.items?.map((item, index) => (
                              <div key={index} className="bg-white p-3 rounded-md shadow-sm border">
                                {/* Corrected key from item_name to name */}
                                <p className="font-medium">Item: {item.name}</p>
                                <Badge variant="secondary">Quantity: {item.quantity}</Badge>
                              </div>
                            ))}
                          </div>
                        </td>
                      </tr>
                    )}
                  </>
                ))}
              </tbody>
            </table>
          </div>

          <div className="flex justify-between items-center mt-4">
            <Button disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
              Previous
            </Button>
            <span>
              Page {page} of {totalPages}
            </span>
            <Button disabled={page >= totalPages} onClick={() => setPage((p) => p + 1)}>
              Next
            </Button>
          </div>
        </>
      )}
    </div>
  );
}