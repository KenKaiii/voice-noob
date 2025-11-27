"use client";

/* eslint-disable no-console -- Debug logging is intentional for WebRTC/audio troubleshooting */

import { useState, useRef, useEffect, useCallback } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { fetchAgents, updateAgent } from "@/lib/api/agents";
import { Button } from "@/components/ui/button";
import { Play, Save } from "lucide-react";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Slider } from "@/components/ui/slider";
import { Switch } from "@/components/ui/switch";
import { Separator } from "@/components/ui/separator";
import { RealtimeAgent, RealtimeSession, type RealtimeItem } from "@openai/agents/realtime";

type TranscriptItem = {
  id: string;
  speaker: "user" | "assistant" | "system";
  text: string;
  timestamp: Date;
};

// WebRTC resources for proper cleanup
type WebRTCResources = {
  peerConnection: RTCPeerConnection | null;
  dataChannel: RTCDataChannel | null;
  audioStream: MediaStream | null;
  audioElement: HTMLAudioElement | null;
};

// Toggle button group component
function ToggleGroup({
  options,
  value,
  onChange,
}: {
  options: { value: string; label: string }[];
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <div className="flex rounded-lg border bg-muted/50 p-1">
      {options.map((option) => (
        <button
          key={option.value}
          onClick={() => onChange(option.value)}
          className={`flex-1 rounded-md px-3 py-1.5 text-sm transition-colors ${
            value === option.value
              ? "bg-background text-foreground shadow-sm"
              : "text-muted-foreground hover:text-foreground"
          }`}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}

export default function TestAgentPage() {
  const [selectedAgentId, setSelectedAgentId] = useState<string>("");
  const [isConnected, setIsConnected] = useState(false);
  const [transcript, setTranscript] = useState<TranscriptItem[]>([]);
  const [callDuration, setCallDuration] = useState(0);

  // Settings state
  const [voice, setVoice] = useState("alloy");
  const [turnDetection, setTurnDetection] = useState("normal");
  const [threshold, setThreshold] = useState(0.5);
  const [prefixPadding, setPrefixPadding] = useState(300);
  const [silenceDuration, setSilenceDuration] = useState(500);
  const [idleTimeout, setIdleTimeout] = useState(true);
  const [editedSystemPrompt, setEditedSystemPrompt] = useState("");

  const queryClient = useQueryClient();

  const sessionRef = useRef<RealtimeSession | null>(null);
  const transcriptEndRef = useRef<HTMLDivElement | null>(null);
  const callTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // WebRTC resource refs for proper cleanup
  const webrtcRef = useRef<WebRTCResources>({
    peerConnection: null,
    dataChannel: null,
    audioStream: null,
    audioElement: null,
  });

  // Batch transcript updates to reduce re-renders
  const pendingTranscriptsRef = useRef<TranscriptItem[]>([]);
  const flushTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Auto-scroll to bottom when transcript updates
  useEffect(() => {
    transcriptEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [transcript]);

  // Fetch agents from API
  const { data: agents = [] } = useQuery({
    queryKey: ["agents"],
    queryFn: fetchAgents,
  });

  // Update all settings when agent changes
  useEffect(() => {
    const agent = agents.find((a) => a.id === selectedAgentId);
    if (agent) {
      setEditedSystemPrompt(agent.system_prompt || "");
      setVoice(agent.voice || "alloy");
      setTurnDetection(agent.turn_detection_mode || "normal");
      setThreshold(agent.turn_detection_threshold ?? 0.5);
      setPrefixPadding(agent.turn_detection_prefix_padding_ms ?? 300);
      setSilenceDuration(agent.turn_detection_silence_duration_ms ?? 500);
    } else {
      setEditedSystemPrompt("");
      setVoice("alloy");
      setTurnDetection("normal");
      setThreshold(0.5);
      setPrefixPadding(300);
      setSilenceDuration(500);
    }
  }, [selectedAgentId, agents]);

  // Mutation to save all settings
  const saveSettingsMutation = useMutation({
    mutationFn: async () => {
      if (!selectedAgentId) throw new Error("No agent selected");
      return updateAgent(selectedAgentId, {
        system_prompt: editedSystemPrompt,
        voice: voice,
        turn_detection_mode: turnDetection as "normal" | "semantic" | "disabled",
        turn_detection_threshold: threshold,
        turn_detection_prefix_padding_ms: prefixPadding,
        turn_detection_silence_duration_ms: silenceDuration,
      });
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["agents"] });
      toast.success("Settings saved");
    },
    onError: (error: Error) => {
      toast.error(`Failed to save: ${error.message}`);
    },
  });

  const selectedAgent = agents.find((a) => a.id === selectedAgentId);
  const hasUnsavedChanges = selectedAgent
    ? selectedAgent.system_prompt !== editedSystemPrompt ||
      selectedAgent.voice !== voice ||
      selectedAgent.turn_detection_mode !== turnDetection ||
      selectedAgent.turn_detection_threshold !== threshold ||
      selectedAgent.turn_detection_prefix_padding_ms !== prefixPadding ||
      selectedAgent.turn_detection_silence_duration_ms !== silenceDuration
    : false;

  const handleSaveSettings = () => {
    saveSettingsMutation.mutate();
  };

  // Flush pending transcript updates
  const flushTranscripts = useCallback(() => {
    if (pendingTranscriptsRef.current.length > 0) {
      const pending = [...pendingTranscriptsRef.current];
      pendingTranscriptsRef.current = [];
      setTranscript((prev) => {
        // Deduplicate by checking existing texts
        const existingTexts = new Set(prev.map((t) => `${t.speaker}:${t.text}`));
        const newItems = pending.filter(
          (item) => !existingTexts.has(`${item.speaker}:${item.text}`)
        );
        return [...prev, ...newItems];
      });
    }
  }, []);

  // Batched addTranscript that groups updates
  const addTranscriptBatched = useCallback(
    (speaker: "user" | "assistant" | "system", text: string) => {
      pendingTranscriptsRef.current.push({
        id: crypto.randomUUID(),
        speaker,
        text,
        timestamp: new Date(),
      });

      // Debounce flush - wait 50ms for more items before flushing
      if (flushTimeoutRef.current) {
        clearTimeout(flushTimeoutRef.current);
      }
      flushTimeoutRef.current = setTimeout(flushTranscripts, 50);
    },
    [flushTranscripts]
  );

  const cleanup = useCallback(() => {
    // Clear call timer
    if (callTimerRef.current) {
      clearInterval(callTimerRef.current);
      callTimerRef.current = null;
    }

    // Clear any pending flush timeout
    if (flushTimeoutRef.current) {
      clearTimeout(flushTimeoutRef.current);
      flushTimeoutRef.current = null;
    }

    // Flush any remaining transcripts
    flushTranscripts();

    // Clean up WebRTC resources
    const { peerConnection, dataChannel, audioStream, audioElement } = webrtcRef.current;

    if (dataChannel) {
      try {
        dataChannel.close();
      } catch (e) {
        console.error("[Cleanup] Error closing data channel:", e);
      }
    }

    if (peerConnection) {
      try {
        peerConnection.close();
      } catch (e) {
        console.error("[Cleanup] Error closing peer connection:", e);
      }
    }

    if (audioStream) {
      try {
        audioStream.getTracks().forEach((track) => track.stop());
      } catch (e) {
        console.error("[Cleanup] Error stopping audio tracks:", e);
      }
    }

    if (audioElement) {
      try {
        audioElement.srcObject = null;
        audioElement.remove();
      } catch (e) {
        console.error("[Cleanup] Error cleaning up audio element:", e);
      }
    }

    // Reset refs
    webrtcRef.current = {
      peerConnection: null,
      dataChannel: null,
      audioStream: null,
      audioElement: null,
    };

    // Clean up session ref
    if (sessionRef.current) {
      try {
        sessionRef.current.close();
      } catch (e) {
        console.error("[Cleanup] Error closing session:", e);
      }
      sessionRef.current = null;
    }
  }, [flushTranscripts]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      cleanup();
    };
  }, [cleanup]);

  // Immediate addTranscript for critical messages (system messages during connect)
  const addTranscriptImmediate = useCallback(
    (speaker: "user" | "assistant" | "system", text: string) => {
      setTranscript((prev) => [
        ...prev,
        {
          id: crypto.randomUUID(),
          speaker,
          text,
          timestamp: new Date(),
        },
      ]);
    },
    []
  );

  // Use batched version for high-frequency updates (history_updated handler)
  const addTranscript = addTranscriptBatched;

  const handleConnect = async () => {
    if (isConnected) {
      // Disconnect
      cleanup();
      setIsConnected(false);
      setCallDuration(0);
      addTranscript("system", "Session ended");
      return;
    }

    if (!selectedAgentId) {
      toast.error("Please select an agent first");
      return;
    }

    const selectedAgent = agents.find((a) => a.id === selectedAgentId);
    if (!selectedAgent) return;

    try {
      addTranscriptImmediate("system", `Connecting to ${selectedAgent.name}...`);

      const agentSystemPrompt = editedSystemPrompt || "You are a helpful voice assistant.";

      // Create a RealtimeAgent with the agent's configuration
      const realtimeAgent = new RealtimeAgent({
        name: selectedAgent.name,
        instructions: agentSystemPrompt,
      });

      // Create a RealtimeSession with WebRTC transport
      const session = new RealtimeSession(realtimeAgent, {
        transport: "webrtc",
      });

      sessionRef.current = session;

      // Set up event listeners
      session.on("transport_event", (event) => {
        console.log("[Transport Event]", event.type, event);

        if (event.type === "connection_change") {
          const status = (event as { type: string; status?: string }).status;
          console.log("[Connection Change]", status);
          if (status === "connected") {
            setIsConnected(true);
          } else if (status === "disconnected") {
            setIsConnected(false);
          }
        } else if (event.type === "error") {
          console.error("[Transport Error]", event);
          const errorEvent = event as { type: string; error?: unknown };
          addTranscript("system", `Error: ${String(errorEvent.error)}`);
        }
      });

      session.on("error", (error) => {
        console.error("[Session Error]", error);
        addTranscript("system", `Session Error: ${String(error.error)}`);
      });

      session.on("history_updated", (history: RealtimeItem[]) => {
        console.log("[History Updated]", history.length, "items");

        // Process history to extract transcripts - use batched updates
        for (const item of history) {
          if (item.type === "message") {
            const messageItem = item as RealtimeItem & {
              role?: string;
              content?: Array<{ type: string; text?: string; transcript?: string }>;
            };
            const role = messageItem.role;
            const content = messageItem.content;

            if (content && Array.isArray(content)) {
              for (const part of content) {
                if (part.type === "input_text" && part.text) {
                  addTranscriptBatched("user", part.text);
                } else if (part.type === "text" && part.text && role === "assistant") {
                  addTranscriptBatched("assistant", part.text);
                } else if (part.type === "input_audio" && part.transcript) {
                  addTranscriptBatched("user", part.transcript);
                } else if (part.type === "audio" && part.transcript && role === "assistant") {
                  addTranscriptBatched("assistant", part.transcript);
                }
              }
            }
          }
        }
      });

      session.on("agent_start", (_context, agent) => {
        console.log("[Agent Start]", agent.name);
      });

      // Fetch ephemeral token from our backend
      const apiBase = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
      const authToken = localStorage.getItem("access_token");
      const tokenResponse = await fetch(`${apiBase}/api/v1/realtime/token/${selectedAgentId}`, {
        headers: authToken ? { Authorization: `Bearer ${authToken}` } : {},
      });

      if (!tokenResponse.ok) {
        const errorText = await tokenResponse.text();
        throw new Error(`Failed to get token: ${errorText}`);
      }

      const tokenData = await tokenResponse.json();
      const ephemeralKey = tokenData.client_secret?.value;

      if (!ephemeralKey) {
        throw new Error("No ephemeral key received from server");
      }

      console.log("[WebRTC] Got ephemeral token:", ephemeralKey.substring(0, 10) + "...");

      // Manual WebRTC connection since SDK doesn't include required OpenAI-Beta header
      const pc = new RTCPeerConnection();
      const audioStream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const audioTrack = audioStream.getAudioTracks()[0];
      if (audioTrack) {
        pc.addTrack(audioTrack);
      }

      // Create data channel for events
      const dataChannel = pc.createDataChannel("oai-events");

      // Set up audio playback
      const audioElement = document.createElement("audio");
      audioElement.autoplay = true;
      pc.ontrack = (event) => {
        audioElement.srcObject = event.streams[0] ?? null;
      };

      // Store WebRTC resources in refs for proper cleanup
      webrtcRef.current = {
        peerConnection: pc,
        dataChannel,
        audioStream,
        audioElement,
      };

      // Create offer
      const offer = await pc.createOffer();
      await pc.setLocalDescription(offer);

      // Connect to OpenAI Realtime API with required header
      const response = await fetch("https://api.openai.com/v1/realtime/calls", {
        method: "POST",
        body: offer.sdp,
        headers: {
          "Content-Type": "application/sdp",
          Authorization: `Bearer ${ephemeralKey}`,
          "OpenAI-Beta": "realtime=v1",
        },
      });

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`OpenAI API error (${response.status}): ${errorText}`);
      }

      const answerSdp = await response.text();
      console.log("[WebRTC] Got SDP answer, setting remote description...");

      await pc.setRemoteDescription({ type: "answer", sdp: answerSdp });
      console.log("[WebRTC] Remote description set!");

      // Handle data channel events
      dataChannel.onopen = () => {
        console.log("[WebRTC] Data channel opened!");
        setIsConnected(true);

        // Start call timer
        setCallDuration(0);
        callTimerRef.current = setInterval(() => {
          setCallDuration((prev) => prev + 1);
        }, 1000);

        // Get tools from token response
        const tools = tokenData.tools ?? [];

        console.log("[WebRTC] Configuring session with", tools.length, "tools");

        // Send session update with agent config and tools
        const instructions = editedSystemPrompt || "You are a helpful voice assistant.";
        const sessionUpdate = {
          type: "session.update",
          session: {
            instructions: instructions,
            voice: voice,
            input_audio_transcription: { model: "whisper-1" },
            turn_detection:
              turnDetection === "disabled"
                ? null
                : {
                    type: turnDetection === "semantic" ? "semantic_vad" : "server_vad",
                    threshold: threshold,
                    prefix_padding_ms: prefixPadding,
                    silence_duration_ms: silenceDuration,
                  },
            tools: tools,
            tool_choice: tools.length > 0 ? "auto" : "none",
          },
        };
        dataChannel.send(JSON.stringify(sessionUpdate));
        console.log(
          "[WebRTC] Sent session.update with tools:",
          tools.map((t: { name: string }) => t.name)
        );
      };

      dataChannel.onmessage = async (event) => {
        try {
          const data = JSON.parse(event.data);
          console.log("[WebRTC] Event:", data.type, data);

          // Handle session.updated confirmation
          if (data.type === "session.updated") {
            const toolsConfigured = data.session?.tools?.length ?? 0;
            console.log("[WebRTC] Session updated - tools configured:", toolsConfigured);
          }

          // Handle transcription
          if (data.type === "conversation.item.input_audio_transcription.completed") {
            addTranscript("user", data.transcript);
          } else if (data.type === "response.audio_transcript.done") {
            addTranscript("assistant", data.transcript);
          } else if (data.type === "response.function_call_arguments.done") {
            // Handle function/tool call
            const { call_id, name, arguments: argsJson } = data;
            console.log("[WebRTC] Function call:", name, argsJson);

            try {
              // Execute tool via backend API
              const toolResponse = await fetch(`${apiBase}/api/v1/tools/execute`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                  tool_name: name,
                  arguments: JSON.parse(argsJson),
                  agent_id: selectedAgentId,
                }),
              });

              const toolResult = await toolResponse.json();
              console.log("[WebRTC] Tool result:", toolResult);

              // Send function call output back to the model
              const outputEvent = {
                type: "conversation.item.create",
                item: {
                  type: "function_call_output",
                  call_id: call_id,
                  output: JSON.stringify(toolResult),
                },
              };
              dataChannel.send(JSON.stringify(outputEvent));

              // Trigger response generation
              const responseCreate = { type: "response.create" };
              dataChannel.send(JSON.stringify(responseCreate));
            } catch (toolError) {
              console.error("[WebRTC] Tool execution error:", toolError);
              // Send error output
              const errorOutput = {
                type: "conversation.item.create",
                item: {
                  type: "function_call_output",
                  call_id: call_id,
                  output: JSON.stringify({ success: false, error: String(toolError) }),
                },
              };
              dataChannel.send(JSON.stringify(errorOutput));
              dataChannel.send(JSON.stringify({ type: "response.create" }));
            }
          } else if (data.type === "error") {
            console.error("[WebRTC] Error event:", data);
            addTranscript("system", `Error: ${data.error?.message ?? "Unknown error"}`);
          }
        } catch (e) {
          console.error("[WebRTC] Failed to parse message:", e);
        }
      };

      dataChannel.onerror = (event) => {
        console.error("[WebRTC] Data channel error:", event);
      };

      dataChannel.onclose = () => {
        console.log("[WebRTC] Data channel closed");
        setIsConnected(false);
        if (callTimerRef.current) {
          clearInterval(callTimerRef.current);
          callTimerRef.current = null;
        }
      };

      pc.onconnectionstatechange = () => {
        console.log("[WebRTC] Connection state:", pc.connectionState);
        if (pc.connectionState === "disconnected" || pc.connectionState === "failed") {
          cleanup();
          setIsConnected(false);
          setCallDuration(0);
        }
      };
    } catch (error: unknown) {
      const err = error as Error;
      console.error("[WebRTC] Connection error:", err);
      addTranscript("system", `Error: ${err.message}`);
      cleanup();

      if (err.name === "NotAllowedError") {
        toast.error(
          "Microphone access denied. Please allow microphone access in your browser settings."
        );
      } else {
        toast.error(`Connection failed: ${err.message}`);
      }
    }
  };

  const handleConnectClick = () => {
    void handleConnect();
  };

  const formatDuration = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`;
  };

  return (
    <div className="flex h-[calc(100vh-4rem)]">
      {/* Main Content */}
      <div className="flex flex-1 overflow-hidden">
        {/* Left - Transcript */}
        <div className="flex flex-1 flex-col">
          <ScrollArea className="flex-1 p-6">
            {transcript.length === 0 ? (
              <div className="flex h-full items-center justify-center text-muted-foreground">
                Start a session to see the conversation
              </div>
            ) : (
              <div className="space-y-6">
                {transcript.map((item) => (
                  <div key={item.id} className="flex gap-4">
                    <div className="w-16 shrink-0 pt-0.5 text-xs font-medium text-muted-foreground">
                      {item.timestamp.toLocaleTimeString([], {
                        hour: "2-digit",
                        minute: "2-digit",
                      })}
                    </div>
                    <div className="flex-1">
                      <div
                        className={`mb-1 text-xs font-semibold uppercase tracking-wide ${
                          item.speaker === "user"
                            ? "text-blue-500"
                            : item.speaker === "assistant"
                              ? "text-green-500"
                              : "text-muted-foreground"
                        }`}
                      >
                        {item.speaker === "user"
                          ? "USER"
                          : item.speaker === "assistant"
                            ? "ASSISTANT"
                            : "SYSTEM"}
                      </div>
                      <div
                        className={`text-sm ${item.speaker === "system" ? "italic text-muted-foreground" : ""}`}
                      >
                        {item.text}
                      </div>
                    </div>
                  </div>
                ))}
                <div ref={transcriptEndRef} />
              </div>
            )}
          </ScrollArea>

          {/* Bottom Control Bar */}
          <div className="border-t bg-muted/30 px-6 py-4">
            <div className="flex items-center justify-center gap-4">
              <div className="flex items-center gap-2 font-mono text-sm text-muted-foreground">
                <span>{formatDuration(callDuration)}</span>
                {isConnected && (
                  <div className="flex h-6 items-center gap-0.5">
                    {[...Array(12)].map((_, i) => (
                      <div
                        key={i}
                        className="w-0.5 animate-pulse bg-foreground/40"
                        style={{
                          height: `${Math.random() * 16 + 4}px`,
                          animationDelay: `${i * 50}ms`,
                        }}
                      />
                    ))}
                  </div>
                )}
              </div>

              <Button
                onClick={handleConnectClick}
                variant={isConnected ? "secondary" : "default"}
                className="gap-2"
                disabled={!selectedAgentId && !isConnected}
              >
                <Play className="h-4 w-4" />
                {isConnected ? "Stop" : "Start session"}
              </Button>
            </div>
          </div>
        </div>

        {/* Right - Settings Panel */}
        <div className="w-[380px] shrink-0 overflow-y-auto border-l bg-muted/20">
          <div className="space-y-6 p-6">
            {/* Agent Selection */}
            <div className="space-y-2">
              <Label className="text-sm font-medium">Agent</Label>
              <Select value={selectedAgentId} onValueChange={setSelectedAgentId}>
                <SelectTrigger>
                  <SelectValue placeholder="Select an agent" />
                </SelectTrigger>
                <SelectContent>
                  {agents
                    .filter((agent) => agent.pricing_tier === "premium")
                    .map((agent) => (
                      <SelectItem key={agent.id} value={agent.id}>
                        {agent.name}
                      </SelectItem>
                    ))}
                </SelectContent>
              </Select>
            </div>

            <Separator />

            {/* System Instructions */}
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <Label className="text-sm font-medium">System instructions</Label>
                {hasUnsavedChanges && selectedAgentId && (
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-7 gap-1 text-xs"
                    onClick={handleSaveSettings}
                    disabled={saveSettingsMutation.isPending}
                  >
                    <Save className="h-3 w-3" />
                    {saveSettingsMutation.isPending ? "Saving..." : "Save"}
                  </Button>
                )}
              </div>
              {selectedAgentId ? (
                <Textarea
                  value={editedSystemPrompt}
                  onChange={(e) => setEditedSystemPrompt(e.target.value)}
                  className="h-[100px] resize-none text-xs"
                  placeholder="Enter system instructions..."
                />
              ) : (
                <div className="flex h-[100px] items-center justify-center rounded-md border bg-muted/50 p-2 text-xs italic text-muted-foreground">
                  Select an agent to edit system instructions
                </div>
              )}
            </div>

            <Separator />

            {/* Voice */}
            <div className="space-y-2">
              <Label className="text-sm font-medium">Voice</Label>
              <Select value={voice} onValueChange={setVoice}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="alloy">Alloy</SelectItem>
                  <SelectItem value="echo">Echo</SelectItem>
                  <SelectItem value="fable">Fable</SelectItem>
                  <SelectItem value="onyx">Onyx</SelectItem>
                  <SelectItem value="nova">Nova</SelectItem>
                  <SelectItem value="shimmer">Shimmer</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <Separator />

            {/* Turn Detection */}
            <div className="space-y-4">
              <Label className="text-sm font-medium">Automatic turn detection</Label>
              <ToggleGroup
                options={[
                  { value: "normal", label: "Normal" },
                  { value: "semantic", label: "Semantic" },
                  { value: "disabled", label: "Disabled" },
                ]}
                value={turnDetection}
                onChange={setTurnDetection}
              />

              {turnDetection !== "disabled" && (
                <div className="space-y-4 pt-2">
                  <div className="space-y-2">
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-muted-foreground">Threshold</span>
                      <span>{threshold.toFixed(2)}</span>
                    </div>
                    <Slider
                      value={[threshold]}
                      onValueChange={(values) => setThreshold(values[0] ?? 0.5)}
                      min={0}
                      max={1}
                      step={0.01}
                    />
                  </div>

                  <div className="space-y-2">
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-muted-foreground">Prefix padding</span>
                      <span>{prefixPadding} ms</span>
                    </div>
                    <Slider
                      value={[prefixPadding]}
                      onValueChange={(values) => setPrefixPadding(values[0] ?? 300)}
                      min={0}
                      max={1000}
                      step={10}
                    />
                  </div>

                  <div className="space-y-2">
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-muted-foreground">Silence duration</span>
                      <span>{silenceDuration} ms</span>
                    </div>
                    <Slider
                      value={[silenceDuration]}
                      onValueChange={(values) => setSilenceDuration(values[0] ?? 500)}
                      min={0}
                      max={2000}
                      step={50}
                    />
                  </div>

                  <div className="flex items-center justify-between">
                    <span className="text-sm text-muted-foreground">Idle timeout</span>
                    <Switch checked={idleTimeout} onCheckedChange={setIdleTimeout} />
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
