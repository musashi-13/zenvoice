import { createFileRoute } from '@tanstack/react-router';
import { useForm } from '@tanstack/react-form';
import { z } from 'zod';
import {
    Card,
    CardHeader,
    CardTitle,
    CardContent,
    CardFooter,
} from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Plus, Trash } from 'lucide-react';

// Define the Zod schema for a single item
const itemSchema = z.object({
    name: z.string({ required_error: 'Item name is required.' }).min(1, 'Item name is required.'),
    quantity: z.number({ required_error: 'Quantity is required.' }).min(1, 'Quantity must be at least 1.'),
});

// Define the Zod schema for the entire form
const warehouseReceiptSchema = z.object({
    receipt_number: z.string({ required_error: 'Receipt number is required.' }).min(1, 'Receipt number is required.'),
    po_number: z.string({ required_error: 'PO number is required.' }).min(1, 'PO number is required.'),
    items: z.array(itemSchema).min(1, 'At least one item is required.'),
});

export const Route = createFileRoute('/warehouse/receipts_/add')({
    component: RouteComponent,
});

function RouteComponent() {
    const form = useForm({
        defaultValues: {
            receipt_number: '',
            po_number: '',
            items: [{ name: '', quantity: 1 }],
        },
        onSubmit: async ({ value }) => {
            // Final validation check on submit
            const parsed = warehouseReceiptSchema.safeParse(value);
            if (!parsed.success) {
                console.error("Submission failed validation", parsed.error.flatten());
                return;
            }

            const payload = {
                ...parsed.data,
                warehouse_id: 'WH001',
                emp_id: 'EMP001003',
            };

            try {
                const response = await fetch('http://localhost:4000/api/receipts/add', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload),
                });

                if (!response.ok) {
                    throw new Error('Failed to save receipt');
                }

                const data = await response.json();
                console.log('Receipt saved:', data);
                alert('Form submitted successfully!');
                form.reset();
            } catch (error) {
                console.error('Error submitting receipt:', error);
                alert('Failed to save receipt. Please try again.');
            }
        },
        validators: {
            onChange: ({ value }) => {
                const result = warehouseReceiptSchema.safeParse(value);
                if (!result.success) {
                    return result.error.flatten().fieldErrors;
                }
                return undefined;
            },
        },
    });

    const addItem = () => {
        form.pushFieldValue('items', { name: '', quantity: 1 });
    };

    const removeItem = (index: number) => {
        form.removeFieldValue('items', index);
    };

    return (
        <div className="flex items-center justify-center min-h-screen bg-gray-100 p-4">
            <Card className="w-full max-w-3xl">
                <CardHeader>
                    <CardTitle>Add Warehouse Receipt</CardTitle>
                </CardHeader>
                <form
                    onSubmit={(e) => {
                        e.preventDefault();
                        e.stopPropagation();
                        form.handleSubmit();
                    }}
                >
                    <CardContent className="space-y-6">
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                            <form.Field
                                name="receipt_number"
                                children={(field) => (
                                    <div className="space-y-2">
                                        <Label htmlFor={field.name}>Receipt Number</Label>
                                        <Input
                                            id={field.name}
                                            name={field.name}
                                            value={field.state.value}
                                            onBlur={field.handleBlur}
                                            onChange={(e) => field.handleChange(e.target.value)}
                                        />
                                        {field.state.meta.errors ? (
                                            <em className="text-red-500 text-sm">{field.state.meta.errors.join(', ')}</em>
                                        ) : null}
                                    </div>
                                )}
                            />
                            <form.Field
                                name="po_number"
                                children={(field) => (
                                    <div className="space-y-2">
                                        <Label htmlFor={field.name}>Purchase Order Number</Label>
                                        <Input
                                            id={field.name}
                                            name={field.name}
                                            value={field.state.value}
                                            onBlur={field.handleBlur}
                                            onChange={(e) => field.handleChange(e.target.value)}
                                        />
                                        {field.state.meta.errors ? (
                                            <em className="text-red-500 text-sm">{field.state.meta.errors.join(', ')}</em>
                                        ) : null}
                                    </div>
                                )}
                            />
                        </div>

                        <div>
                            <h3 className="text-lg font-semibold mb-4">Items</h3>
                            <form.Field
                                name="items"
                                children={(itemsField) => (
                                    <>
                                        {itemsField.state.value.map((_, index) => (
                                            <div key={index} className="flex items-end gap-4 mb-4">
                                                <form.Field
                                                    name={`items[${index}].name`}
                                                    children={(field) => (
                                                        <div className="flex-grow space-y-2">
                                                            <Label htmlFor={field.name}>Item Name</Label>
                                                            <Input
                                                                id={field.name}
                                                                name={field.name}
                                                                value={field.state.value}
                                                                onBlur={field.handleBlur}
                                                                onChange={(e) => field.handleChange(e.target.value)}
                                                            />
                                                            {field.state.meta.errors ? (
                                                                <em className="text-red-500 text-sm">{field.state.meta.errors.join(', ')}</em>
                                                            ) : null}
                                                        </div>
                                                    )}
                                                />
                                                <form.Field
                                                    name={`items[${index}].quantity`}
                                                    children={(field) => (
                                                        <div className="space-y-2">
                                                            <Label htmlFor={field.name}>Quantity</Label>
                                                            <Input
                                                                id={field.name}
                                                                name={field.name}
                                                                type="number"
                                                                value={field.state.value}
                                                                onBlur={field.handleBlur}
                                                                onChange={(e) => field.handleChange(Number(e.target.value) || 0)}
                                                                min="1"
                                                            />
                                                            {field.state.meta.errors ? (
                                                                <em className="text-red-500 text-sm">{field.state.meta.errors.join(', ')}</em>
                                                            ) : null}
                                                        </div>
                                                    )}
                                                />
                                                <Button
                                                    className='mb-2'
                                                    type="button"
                                                    variant="destructive"
                                                    size="icon"
                                                    onClick={() => removeItem(index)}
                                                    disabled={itemsField.state.value.length <= 1}
                                                >
                                                    <Trash className="h-4 w-4" />
                                                </Button>
                                            </div>
                                        ))}
                                        {itemsField.state.meta.errors ? (
                                            <em className="text-red-500 text-sm">{itemsField.state.meta.errors.join(', ')}</em>
                                        ) : null}
                                    </>
                                )}
                            />
                            <Button type="button" variant="outline" onClick={addItem} className="mt-2">
                                <Plus className="h-4 w-4 mr-2" />
                                Add Item
                            </Button>
                        </div>
                    </CardContent>
                    <CardFooter className="flex justify-end">
                        <form.Subscribe
                            selector={(state) => [state.canSubmit, state.isSubmitting]}
                            children={([canSubmit, isSubmitting]) => (
                                <Button type="submit" disabled={!canSubmit || isSubmitting}>
                                    {isSubmitting ? 'Saving...' : 'Save Receipt'}
                                </Button>
                            )}
                        />
                    </CardFooter>
                </form>
            </Card>
        </div>
    );
}
