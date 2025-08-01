import { Link } from '@tanstack/react-router'
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarProvider,
} from "@/components/ui/sidebar"
import {
  FileText,
  ChevronDown,
  FileSearch,
  FileInput,
  ReceiptText,
  House,
  ChartLine,
  Logs,
  PackageSearch,
  HeartPulse,
} from 'lucide-react'
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible'

export default function AdminSidebar() {
  return (
    <div className='shrink-0'>
        <SidebarProvider>
            <Sidebar>
                <SidebarHeader>
                    Admin Panel
                </SidebarHeader>
                <SidebarContent>
                    <SidebarMenu>
                        <SidebarMenuItem>
                            <SidebarMenuButton asChild>
                                <Link to="/admin"> 
                                    <House className="ml-2" />
                                    <span>Home</span> 
                                </Link>
                            </SidebarMenuButton>
                        </SidebarMenuItem>
                        <SidebarMenuItem>
                            <SidebarMenuButton asChild>
                                <Link to="/admin">
                                    <ChartLine className='ml-2'/> 
                                    <span>Analytics</span> 
                                </Link>
                            </SidebarMenuButton>
                        </SidebarMenuItem>
                        <SidebarMenuItem>
                            <SidebarMenuButton asChild>
                                <Link to="/admin">
                                    <Logs className='ml-2'/> 
                                    <span>Logs</span> 
                                </Link>
                            </SidebarMenuButton>
                        </SidebarMenuItem>
                        <Collapsible defaultOpen className="group/collapsible">
                            <SidebarGroup>
                                <SidebarGroupLabel asChild>
                                    <CollapsibleTrigger>
                                        <span>Invoices</span>
                                        <ChevronDown className="ml-auto transition-transform group-data-[state=open]/collapsible:rotate-180" />
                                    </CollapsibleTrigger>
                                </SidebarGroupLabel>
                                <CollapsibleContent>
                                    <SidebarGroupContent>
                                        
                                            <SidebarMenuItem>
                                                <SidebarMenuButton asChild>
                                                    <Link to="/admin/invoices"> 
                                                        <FileText/>
                                                        View All Invoices
                                                    </Link>
                                                </SidebarMenuButton>
                                            </SidebarMenuItem>
                                            <SidebarMenuItem>
                                                <SidebarMenuButton asChild>
                                                    <Link to="/admin/invoices"> 
                                                        <FileSearch/>
                                                        <span>Track Invoice</span>
                                                    </Link>
                                                </SidebarMenuButton>
                                            </SidebarMenuItem>
                                            <SidebarMenuItem>
                                                <SidebarMenuButton asChild>
                                                    <Link to="/admin/invoices"> 
                                                        <FileInput/>
                                                        <span>Update Invoice</span>
                                                    </Link>
                                                </SidebarMenuButton>
                                            </SidebarMenuItem>
                                    </SidebarGroupContent>
                                </CollapsibleContent>
                            </SidebarGroup>
                        </Collapsible>
                        <Collapsible defaultOpen className="group/collapsible">
                            <SidebarGroup>
                                <SidebarGroupLabel asChild>
                                    <CollapsibleTrigger>
                                        <span>Receipts</span>
                                        <ChevronDown className="ml-auto transition-transform group-data-[state=open]/collapsible:rotate-180" />
                                    </CollapsibleTrigger>
                                </SidebarGroupLabel>
                                <CollapsibleContent>
                                    <SidebarGroupContent>
                                        <SidebarMenuItem>
                                            <SidebarMenuButton asChild>
                                                <Link to="/admin/invoices"> 
                                                    <ReceiptText/>
                                                    <span>View All Receipts</span> 
                                                </Link>
                                            </SidebarMenuButton>
                                        </SidebarMenuItem>
                                        <SidebarMenuItem>
                                            <SidebarMenuButton asChild>
                                                <Link to="/admin/invoices"> 
                                                    <FileSearch/>
                                                    <span>Track Invoice</span>
                                                </Link>
                                            </SidebarMenuButton>
                                        </SidebarMenuItem>
                                    </SidebarGroupContent>
                                </CollapsibleContent>
                            </SidebarGroup>
                        </Collapsible>
                        <Collapsible defaultOpen className="group/collapsible">
                            <SidebarGroup>
                                <SidebarGroupLabel asChild>
                                    <CollapsibleTrigger>
                                        <span>Errors</span>
                                        <ChevronDown className="ml-auto transition-transform group-data-[state=open]/collapsible:rotate-180" />
                                    </CollapsibleTrigger>
                                </SidebarGroupLabel>
                                <CollapsibleContent>
                                    <SidebarGroupContent>
                                        <SidebarMenuItem>
                                            <SidebarMenuButton asChild>
                                                <Link to="/admin/invoices"> 
                                                    <HeartPulse/>
                                                    <span>System</span> 
                                                </Link>
                                            </SidebarMenuButton>
                                        </SidebarMenuItem>
                                        <SidebarMenuItem>
                                            <SidebarMenuButton asChild>
                                                <Link to="/admin/invoices"> 
                                                    <PackageSearch/>
                                                    <span>Process</span>
                                                </Link>
                                            </SidebarMenuButton>
                                        </SidebarMenuItem>
                                    </SidebarGroupContent>
                                </CollapsibleContent>
                            </SidebarGroup>
                        </Collapsible>
                    </SidebarMenu>
                </SidebarContent>
                <SidebarFooter>
                    Log Out
                </SidebarFooter>
            </Sidebar>
        </SidebarProvider>
    </div>
    )
}