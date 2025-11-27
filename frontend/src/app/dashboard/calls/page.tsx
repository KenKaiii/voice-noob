"use client";

import { useState, useMemo, useRef } from "react";
import { useDebounce } from "use-debounce";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  History,
  Download,
  Play,
  Pause,
  Loader2,
  AlertCircle,
  ChevronLeft,
  ChevronRight,
} from "lucide-react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { listCalls, type CallRecord } from "@/lib/api/calls";

function formatDuration(seconds: number): string {
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  if (mins === 0) return `${secs}s`;
  return `${mins}m ${secs}s`;
}

function formatPhoneNumber(number: string): string {
  if (number.startsWith("+1") && number.length === 12) {
    return `(${number.slice(2, 5)}) ${number.slice(5, 8)}-${number.slice(8)}`;
  }
  return number;
}

export default function CallHistoryPage() {
  const router = useRouter();
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const [playingCallId, setPlayingCallId] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [debouncedSearchQuery] = useDebounce(searchQuery, 300);
  const [statusFilter, setStatusFilter] = useState("all");
  const [page, setPage] = useState(1);
  const pageSize = 20;

  // Fetch calls from API
  const { data, isLoading, error } = useQuery({
    queryKey: ["calls", page, statusFilter],
    queryFn: () =>
      listCalls({
        page,
        page_size: pageSize,
        status:
          statusFilter !== "all" && !["inbound", "outbound"].includes(statusFilter)
            ? statusFilter
            : undefined,
        direction: ["inbound", "outbound"].includes(statusFilter)
          ? (statusFilter as "inbound" | "outbound")
          : undefined,
      }),
  });

  const callsData = useMemo(() => data?.calls ?? [], [data?.calls]);
  const totalPages = data?.total_pages ?? 0;
  const totalCalls = data?.total ?? 0;

  const handlePlayRecording = (call: CallRecord) => {
    if (!call.recording_url) {
      toast.error("No recording available for this call");
      return;
    }

    // If already playing this call, pause it
    if (playingCallId === call.id && audioRef.current) {
      audioRef.current.pause();
      setPlayingCallId(null);
      return;
    }

    // Stop any currently playing audio
    if (audioRef.current) {
      audioRef.current.pause();
    }

    // Create new audio element and play
    const audio = new Audio(call.recording_url);
    audioRef.current = audio;
    setPlayingCallId(call.id);

    audio.play().catch((err: Error) => {
      toast.error(`Failed to play recording: ${err.message}`);
      setPlayingCallId(null);
    });

    audio.onended = () => {
      setPlayingCallId(null);
    };
  };

  const handleDownloadTranscript = (call: CallRecord) => {
    if (!call.transcript) {
      toast.error("No transcript available for this call");
      return;
    }

    // Create a blob with the transcript text
    const blob = new Blob([call.transcript], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `transcript-${call.id}.txt`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
    toast.success("Transcript download started");
  };

  const handleRowClick = (callId: string) => {
    router.push(`/dashboard/calls/${callId}`);
  };

  // Filter calls by search query (client-side for now)
  const filteredCalls = useMemo(() => {
    if (!debouncedSearchQuery) return callsData;
    return callsData.filter((call) => {
      const searchLower = debouncedSearchQuery.toLowerCase();
      return (
        (call.agent_name?.toLowerCase().includes(searchLower) ?? false) ||
        (call.contact_name?.toLowerCase().includes(searchLower) ?? false) ||
        call.from_number.includes(debouncedSearchQuery) ||
        call.to_number.includes(debouncedSearchQuery)
      );
    });
  }, [callsData, debouncedSearchQuery]);

  const getStatusBadgeVariant = (status: string) => {
    switch (status) {
      case "completed":
        return "default";
      case "failed":
      case "busy":
      case "no_answer":
        return "destructive";
      case "in_progress":
        return "secondary";
      default:
        return "outline";
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Call History</h1>
        <p className="text-muted-foreground">View and analyze your voice agent call logs</p>
      </div>

      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>Recent Calls</CardTitle>
              <CardDescription>
                {isLoading
                  ? "Loading..."
                  : totalCalls === 0
                    ? "No calls yet"
                    : `${totalCalls} total calls`}
              </CardDescription>
            </div>
            <div className="flex gap-2">
              <Input
                placeholder="Search calls..."
                className="w-[250px]"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
              />
              <Select
                value={statusFilter}
                onValueChange={(value) => {
                  setStatusFilter(value);
                  setPage(1); // Reset to first page when filter changes
                }}
              >
                <SelectTrigger className="w-[150px]">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Calls</SelectItem>
                  <SelectItem value="completed">Completed</SelectItem>
                  <SelectItem value="failed">Failed</SelectItem>
                  <SelectItem value="in_progress">In Progress</SelectItem>
                  <SelectItem value="inbound">Inbound</SelectItem>
                  <SelectItem value="outbound">Outbound</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="flex flex-col items-center justify-center py-16">
              <Loader2 className="mb-4 h-16 w-16 animate-spin text-muted-foreground/50" />
              <p className="text-muted-foreground">Loading calls...</p>
            </div>
          ) : error instanceof Error ? (
            <div className="flex flex-col items-center justify-center py-16">
              <AlertCircle className="mb-4 h-16 w-16 text-destructive" />
              <h3 className="mb-2 text-lg font-semibold">Failed to load calls</h3>
              <p className="max-w-sm text-center text-sm text-muted-foreground">{error.message}</p>
            </div>
          ) : callsData.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-16">
              <History className="mb-4 h-16 w-16 text-muted-foreground/50" />
              <h3 className="mb-2 text-lg font-semibold">No calls yet</h3>
              <p className="max-w-sm text-center text-sm text-muted-foreground">
                Call history will appear here once your voice agents start handling calls
              </p>
            </div>
          ) : filteredCalls.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-16">
              <History className="mb-4 h-16 w-16 text-muted-foreground/50" />
              <h3 className="mb-2 text-lg font-semibold">No matching calls found</h3>
              <p className="max-w-sm text-center text-sm text-muted-foreground">
                Try adjusting your search or filter criteria
              </p>
            </div>
          ) : (
            <>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Date & Time</TableHead>
                    <TableHead>Agent</TableHead>
                    <TableHead>Direction</TableHead>
                    <TableHead>From/To</TableHead>
                    <TableHead>Duration</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead className="w-[100px]">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredCalls.map((call) => (
                    <TableRow
                      key={call.id}
                      className="cursor-pointer"
                      onClick={() => handleRowClick(call.id)}
                    >
                      <TableCell className="text-sm">
                        {new Date(call.started_at).toLocaleString()}
                      </TableCell>
                      <TableCell className="font-medium">
                        {call.agent_name ?? "Unknown Agent"}
                      </TableCell>
                      <TableCell>
                        <Badge variant={call.direction === "inbound" ? "default" : "secondary"}>
                          {call.direction}
                        </Badge>
                      </TableCell>
                      <TableCell className="font-mono text-xs">
                        {call.direction === "inbound"
                          ? formatPhoneNumber(call.from_number)
                          : formatPhoneNumber(call.to_number)}
                        {call.contact_name && (
                          <span className="ml-2 text-muted-foreground">({call.contact_name})</span>
                        )}
                      </TableCell>
                      <TableCell>{formatDuration(call.duration_seconds)}</TableCell>
                      <TableCell>
                        <Badge variant={getStatusBadgeVariant(call.status)}>
                          {call.status.replace("_", " ")}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <div className="flex gap-1">
                          {call.recording_url && (
                            <Button
                              variant="ghost"
                              size="icon"
                              title={
                                playingCallId === call.id ? "Pause recording" : "Play recording"
                              }
                              onClick={(e) => {
                                e.stopPropagation();
                                handlePlayRecording(call);
                              }}
                            >
                              {playingCallId === call.id ? (
                                <Pause className="h-4 w-4" />
                              ) : (
                                <Play className="h-4 w-4" />
                              )}
                            </Button>
                          )}
                          {call.transcript && (
                            <Button
                              variant="ghost"
                              size="icon"
                              title="Download transcript"
                              onClick={(e) => {
                                e.stopPropagation();
                                handleDownloadTranscript(call);
                              }}
                            >
                              <Download className="h-4 w-4" />
                            </Button>
                          )}
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>

              {/* Pagination */}
              {totalPages > 1 && (
                <div className="mt-4 flex items-center justify-between border-t pt-4">
                  <p className="text-sm text-muted-foreground">
                    Page {page} of {totalPages}
                  </p>
                  <div className="flex gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setPage((p) => Math.max(1, p - 1))}
                      disabled={page === 1}
                    >
                      <ChevronLeft className="mr-1 h-4 w-4" />
                      Previous
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                      disabled={page === totalPages}
                    >
                      Next
                      <ChevronRight className="ml-1 h-4 w-4" />
                    </Button>
                  </div>
                </div>
              )}
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
