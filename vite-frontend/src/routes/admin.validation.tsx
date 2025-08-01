import { createFileRoute } from '@tanstack/react-router';
import { useEffect, useState } from 'react';
import {
  useReactTable,
  getCoreRowModel,
  flexRender,
  type ColumnDef,
} from '@tanstack/react-table';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge'; // Using shadcn Badge

export const Route = createFileRoute('/admin/validation')({
  component: RouteComponent,
});

// Define the type for our validator data
type ValidatorStatus = {
  po_number: string;
  invoice_status: string | null;
  invoice_updated_at: string | null;
  invoice_log: string | null;
  receipt_status: string | null;
  receipt_updated_at: string | null;
  receipt_log: string | null;
};

// Helper component to render status badges with appropriate colors
const StatusBadge = ({ status }: { status: string | null }) => {
  if (!status) return <Badge variant="outline">N/A</Badge>;

  const lowerStatus = status.toLowerCase();
  let variant: 'default' | 'secondary' | 'destructive' | 'outline' = 'secondary';

  if (lowerStatus.includes('matched') || lowerStatus.includes('success')) {
    variant = 'default'; // Green in shadcn default theme
  } else if (lowerStatus.includes('pending')) {
    variant = 'secondary'; // Yellow/Gray
  } else if (lowerStatus.includes('failed') || lowerStatus.includes('error')) {
    variant = 'destructive'; // Red
  }

  return <Badge variant={variant}>{status}</Badge>;
};

function RouteComponent() {
  const [data, setData] = useState<ValidatorStatus[]>([]);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [loading, setLoading] = useState(false);

  const fetchData = async (pageNumber: number) => {
    setLoading(true);
    try {
      const res = await fetch(`http://localhost:4000/api/validation?page=${pageNumber}&limit=10`);
      const json = await res.json();
      console.log('Fetched validator status:', json);
      setData(json.data);
      setTotalPages(json.pagination.totalPages);
    } catch (err) {
      console.error('Failed to fetch validator status', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData(page);
  }, [page]);

  const columns: ColumnDef<ValidatorStatus>[] = [
    {
      header: 'PO Number',
      accessorKey: 'po_number',
    },
    {
      header: 'Invoice Status',
      accessorKey: 'invoice_status',
      cell: ({ row }) => <StatusBadge status={row.original.invoice_status} />,
    },
    {
        header: 'Invoice Log',
        accessorKey: 'invoice_log',
        cell: info => <span className="text-xs text-gray-600">{info.getValue<string>() || '—'}</span>,
    },
    {
      header: 'Receipt Status',
      accessorKey: 'receipt_status',
      cell: ({ row }) => <StatusBadge status={row.original.receipt_status} />,
    },
    {
        header: 'Receipt Log',
        accessorKey: 'receipt_log',
        cell: info => <span className="text-xs text-gray-600">{info.getValue<string>() || '—'}</span>,
    },
    {
      header: 'Last Updated (Receipt)',
      accessorKey: 'receipt_updated_at',
      cell: info => {
        const val = info.getValue<string>();
        return val ? new Date(val).toLocaleString() : 'N/A';
      },
    },
  ];

  const table = useReactTable({
    data,
    columns,
    getCoreRowModel: getCoreRowModel(),
    filterFns: {
        fuzzy:  () => {return true}
    }
  });

  return (
    <div className="p-4 sm:p-6 lg:p-8">
      <h1 className="text-2xl font-bold mb-6">Validation Status</h1>
      {loading ? (
        <div className="text-center py-10">Loading...</div>
      ) : (
        <>
          <div className="overflow-x-auto rounded-lg border">
            <table className="w-full border-collapse text-left text-sm">
              <thead className="bg-gray-50">
                {table.getHeaderGroups().map(headerGroup => (
                  <tr key={headerGroup.id}>
                    {headerGroup.headers.map(header => (
                      <th key={header.id} className="px-4 py-3 font-medium text-gray-600">
                        {flexRender(header.column.columnDef.header, header.getContext())}
                      </th>
                    ))}
                  </tr>
                ))}
              </thead>
              <tbody className="divide-y divide-gray-200">
                {table.getRowModel().rows.map(row => (
                  <tr key={row.id} className="hover:bg-gray-50">
                    {row.getVisibleCells().map(cell => (
                      <td key={cell.id} className="px-4 py-3 align-top">
                        {flexRender(cell.column.columnDef.cell, cell.getContext())}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="flex justify-between items-center mt-6">
            <Button size="sm" disabled={page <= 1} onClick={() => setPage(p => p - 1)}>
              Previous
            </Button>
            <span className="text-sm font-medium">
              Page {page} of {totalPages}
            </span>
            <Button size="sm" disabled={page >= totalPages} onClick={() => setPage(p => p + 1)}>
              Next
            </Button>
          </div>
        </>
      )}
    </div>
  );
}