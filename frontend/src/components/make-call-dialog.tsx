"use client";

import { useState, useEffect } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import { Phone, PhoneCall, PhoneOff, Loader2, Clock } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { initiateCall, hangupCall, listPhoneNumbers, type PhoneNumber } from "@/lib/api/telephony";
import type { Agent } from "@/lib/api/agents";

interface MakeCallDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  agent: Agent;
}

type CallState = "idle" | "dialing" | "ringing" | "in_progress" | "ended";

export function MakeCallDialog({ open, onOpenChange, agent }: MakeCallDialogProps) {
  const [phoneNumber, setPhoneNumber] = useState("");
  const [selectedFromNumber, setSelectedFromNumber] = useState<string>("");
  const [callState, setCallState] = useState<CallState>("idle");
  const [callId, setCallId] = useState<string | null>(null);
  const [callDuration, setCallDuration] = useState(0);
  const [provider] = useState<"twilio" | "telnyx">("telnyx");

  // Fetch available phone numbers
  const { data: phoneNumbers = [] } = useQuery({
    queryKey: ["phone-numbers", provider],
    queryFn: () => listPhoneNumbers(provider),
    enabled: open,
  });

  // Set default from number when phone numbers load
  useEffect(() => {
    if (phoneNumbers.length > 0 && !selectedFromNumber) {
      // Prefer the agent's assigned number if available
      const agentNumber = phoneNumbers.find((n) => n.id === agent.phone_number_id);
      const firstNumber = phoneNumbers[0];
      setSelectedFromNumber(agentNumber?.phone_number ?? firstNumber?.phone_number ?? "");
    }
  }, [phoneNumbers, selectedFromNumber, agent.phone_number_id]);

  // Call duration timer
  useEffect(() => {
    let interval: NodeJS.Timeout | null = null;
    if (callState === "in_progress") {
      interval = setInterval(() => {
        setCallDuration((d) => d + 1);
      }, 1000);
    }
    return () => {
      if (interval) clearInterval(interval);
    };
  }, [callState]);

  // Reset state when dialog closes
  useEffect(() => {
    if (!open) {
      setCallState("idle");
      setCallId(null);
      setCallDuration(0);
      setPhoneNumber("");
    }
  }, [open]);

  const initiateMutation = useMutation({
    mutationFn: initiateCall,
    onSuccess: (data) => {
      setCallId(data.call_id);
      setCallState("ringing");
      toast.success("Call initiated");
      // Simulate call being answered after 3 seconds for demo
      // In production, this would be updated via webhooks/polling
      setTimeout(() => {
        setCallState("in_progress");
      }, 3000);
    },
    onError: (error: Error) => {
      setCallState("idle");
      toast.error(`Failed to initiate call: ${error.message}`);
    },
  });

  const hangupMutation = useMutation({
    mutationFn: () => {
      if (!callId) throw new Error("No call to hang up");
      return hangupCall(callId, provider);
    },
    onSuccess: () => {
      setCallState("ended");
      toast.success("Call ended");
      setTimeout(() => {
        onOpenChange(false);
      }, 1500);
    },
    onError: (error: Error) => {
      toast.error(`Failed to hang up: ${error.message}`);
    },
  });

  const handleCall = () => {
    if (!phoneNumber || !selectedFromNumber) {
      toast.error("Please enter a phone number and select a from number");
      return;
    }
    setCallState("dialing");
    initiateMutation.mutate({
      to_number: phoneNumber,
      from_number: selectedFromNumber,
      agent_id: agent.id,
    });
  };

  const handleHangup = () => {
    hangupMutation.mutate();
  };

  const formatDuration = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`;
  };

  const formatPhoneNumber = (number: string) => {
    // Simple formatting for US numbers
    if (number.startsWith("+1") && number.length === 12) {
      return `(${number.slice(2, 5)}) ${number.slice(5, 8)}-${number.slice(8)}`;
    }
    return number;
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Phone className="h-5 w-5" />
            Make a Call
          </DialogTitle>
          <DialogDescription>Call using agent &quot;{agent.name}&quot;</DialogDescription>
        </DialogHeader>

        {callState === "idle" ? (
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="from-number">From Number</Label>
              <Select value={selectedFromNumber} onValueChange={setSelectedFromNumber}>
                <SelectTrigger>
                  <SelectValue placeholder="Select a number" />
                </SelectTrigger>
                <SelectContent>
                  {phoneNumbers.map((num: PhoneNumber) => (
                    <SelectItem key={num.id} value={num.phone_number}>
                      {formatPhoneNumber(num.phone_number)}
                      {num.friendly_name ? ` (${num.friendly_name})` : ""}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {phoneNumbers.length === 0 && (
                <p className="text-xs text-muted-foreground">
                  No phone numbers available. Purchase one in Settings.
                </p>
              )}
            </div>

            <div className="space-y-2">
              <Label htmlFor="to-number">Phone Number to Call</Label>
              <Input
                id="to-number"
                placeholder="+1 (555) 123-4567"
                value={phoneNumber}
                onChange={(e) => setPhoneNumber(e.target.value)}
              />
              <p className="text-xs text-muted-foreground">
                Enter the phone number in E.164 format (e.g., +15551234567)
              </p>
            </div>
          </div>
        ) : (
          <div className="flex flex-col items-center justify-center space-y-4 py-8">
            {callState === "dialing" && (
              <>
                <Loader2 className="h-12 w-12 animate-spin text-primary" />
                <p className="text-lg font-medium">Dialing...</p>
                <p className="text-sm text-muted-foreground">{formatPhoneNumber(phoneNumber)}</p>
              </>
            )}

            {callState === "ringing" && (
              <>
                <PhoneCall className="h-12 w-12 animate-pulse text-yellow-500" />
                <p className="text-lg font-medium">Ringing...</p>
                <p className="text-sm text-muted-foreground">{formatPhoneNumber(phoneNumber)}</p>
              </>
            )}

            {callState === "in_progress" && (
              <>
                <PhoneCall className="h-12 w-12 text-green-500" />
                <p className="text-lg font-medium">Call in Progress</p>
                <div className="flex items-center gap-2 font-mono text-2xl">
                  <Clock className="h-5 w-5" />
                  {formatDuration(callDuration)}
                </div>
                <p className="text-sm text-muted-foreground">{formatPhoneNumber(phoneNumber)}</p>
              </>
            )}

            {callState === "ended" && (
              <>
                <PhoneOff className="h-12 w-12 text-muted-foreground" />
                <p className="text-lg font-medium">Call Ended</p>
                <p className="text-sm text-muted-foreground">
                  Duration: {formatDuration(callDuration)}
                </p>
              </>
            )}
          </div>
        )}

        <DialogFooter>
          {callState === "idle" ? (
            <>
              <Button variant="outline" onClick={() => onOpenChange(false)}>
                Cancel
              </Button>
              <Button
                onClick={handleCall}
                disabled={!phoneNumber || !selectedFromNumber || phoneNumbers.length === 0}
              >
                <Phone className="mr-2 h-4 w-4" />
                Call
              </Button>
            </>
          ) : callState !== "ended" ? (
            <Button
              variant="destructive"
              onClick={handleHangup}
              disabled={hangupMutation.isPending}
              className="w-full"
            >
              <PhoneOff className="mr-2 h-4 w-4" />
              Hang Up
            </Button>
          ) : (
            <Button variant="outline" onClick={() => onOpenChange(false)} className="w-full">
              Close
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
