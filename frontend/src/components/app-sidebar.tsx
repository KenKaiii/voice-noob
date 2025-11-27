"use client";

import * as React from "react";
import {
  Bot,
  Phone,
  History,
  Settings,
  LayoutDashboard,
  Mic,
  Zap,
  Users,
  Calendar,
  FolderOpen,
} from "lucide-react";

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
  SidebarRail,
} from "@/components/ui/sidebar";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/hooks/use-auth";

const navItems = [
  {
    title: "Dashboard",
    url: "/dashboard",
    icon: LayoutDashboard,
  },
  {
    title: "Voice Agents",
    url: "/dashboard/agents",
    icon: Bot,
  },
  {
    title: "Workspaces",
    url: "/dashboard/workspaces",
    icon: FolderOpen,
  },
  {
    title: "CRM",
    url: "/dashboard/crm",
    icon: Users,
  },
  {
    title: "Appointments",
    url: "/dashboard/appointments",
    icon: Calendar,
  },
  {
    title: "Integrations",
    url: "/dashboard/integrations",
    icon: Zap,
  },
  {
    title: "Phone Numbers",
    url: "/dashboard/phone-numbers",
    icon: Phone,
  },
  {
    title: "Call History",
    url: "/dashboard/calls",
    icon: History,
  },
  {
    title: "Test Agent",
    url: "/dashboard/test",
    icon: Mic,
  },
  {
    title: "Settings",
    url: "/dashboard/settings",
    icon: Settings,
  },
];

export function AppSidebar() {
  const pathname = usePathname();
  const { user, logout } = useAuth();

  const displayName = user?.username ?? "User";
  const displayEmail = user?.email ?? "user@example.com";
  const initials = displayName.slice(0, 2).toUpperCase();

  return (
    <Sidebar>
      <SidebarHeader className="border-b px-6 py-4">
        <span className="text-sm font-semibold">Voice Noob</span>
      </SidebarHeader>
      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupLabel>Navigation</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              {navItems.map((item) => (
                <SidebarMenuItem key={item.title}>
                  <SidebarMenuButton asChild isActive={pathname === item.url}>
                    <Link href={item.url}>
                      <item.icon className="h-4 w-4" />
                      <span>{item.title}</span>
                    </Link>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              ))}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>
      <SidebarFooter className="border-t p-4">
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <button className="flex w-full items-center gap-2 rounded-lg px-2 py-2 hover:bg-accent">
              <Avatar className="h-8 w-8">
                <AvatarFallback>{initials}</AvatarFallback>
              </Avatar>
              <div className="flex flex-col text-left text-sm">
                <span className="font-medium">{displayName}</span>
                <span className="text-xs text-muted-foreground">{displayEmail}</span>
              </div>
            </button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-56">
            <DropdownMenuLabel>My Account</DropdownMenuLabel>
            <DropdownMenuSeparator />
            <DropdownMenuItem asChild>
              <Link href="/dashboard/settings">Settings</Link>
            </DropdownMenuItem>
            <DropdownMenuItem asChild>
              <Link href="/dashboard/settings">API Keys</Link>
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem onClick={logout}>Log out</DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </SidebarFooter>
      <SidebarRail />
    </Sidebar>
  );
}
