"use client";

/* eslint-disable no-console -- Debug logging is intentional for WebRTC/audio troubleshooting */

import { useState, useRef, useEffect, useCallback } from "react";
import { useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import { fetchAgents } from "@/lib/api/agents";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Phone, PhoneOff, Mic, MicOff } from "lucide-react";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { RealtimeAgent, RealtimeSession, type RealtimeItem } from "@openai/agents/realtime";

type TranscriptItem = {
  id: string;
  speaker: string;
  text: string;
  timestamp: Date;
};

export default function TestAgentPage() {
  const [selectedAgentId, setSelectedAgentId] = useState<string>("");
  const [isConnected, setIsConnected] = useState(false);
  const [isMuted, setIsMuted] = useState(false);
  const [transcript, setTranscript] = useState<TranscriptItem[]>([]);
  const [audioStatus, setAudioStatus] = useState<string>("Not connected");

  const sessionRef = useRef<RealtimeSession | null>(null);

  // Fetch agents from API
  const { data: agents = [] } = useQuery({
    queryKey: ["agents"],
    queryFn: fetchAgents,
  });

  const cleanup = useCallback(() => {
    if (sessionRef.current) {
      try {
        sessionRef.current.close();
      } catch (e) {
        console.error("[Cleanup] Error closing session:", e);
      }
      sessionRef.current = null;
    }
  }, []);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      cleanup();
    };
  }, [cleanup]);

  const addTranscript = useCallback((speaker: string, text: string) => {
    setTranscript((prev) => [
      ...prev,
      {
        id: crypto.randomUUID(),
        speaker,
        text,
        timestamp: new Date(),
      },
    ]);
  }, []);

  const handleConnect = async () => {
    if (isConnected) {
      // Disconnect
      cleanup();
      setIsConnected(false);
      setAudioStatus("Disconnected");
      addTranscript("System", "Call ended");
      return;
    }

    if (!selectedAgentId) {
      toast.error("Please select an agent first");
      return;
    }

    const selectedAgent = agents.find((a) => a.id === selectedAgentId);
    if (!selectedAgent) return;

    try {
      setAudioStatus("Initializing...");
      addTranscript("System", `Connecting to ${selectedAgent.name}...`);

      // Create a RealtimeAgent with the agent's configuration
      const realtimeAgent = new RealtimeAgent({
        name: selectedAgent.name,
        instructions: selectedAgent.system_prompt || "You are a helpful voice assistant.",
      });

      // Create a RealtimeSession with WebRTC transport
      // Note: model comes from the ephemeral token, not specified here
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
            setAudioStatus("Connected - Voice active");
            addTranscript("System", "WebRTC connected! Speak to test your agent.");
          } else if (status === "disconnected") {
            setIsConnected(false);
            setAudioStatus("Disconnected");
            addTranscript("System", "Connection closed");
          } else if (status === "connecting") {
            setAudioStatus("Connecting...");
          }
        } else if (event.type === "error") {
          console.error("[Transport Error]", event);
          const errorEvent = event as { type: string; error?: unknown };
          addTranscript("System", `Error: ${String(errorEvent.error)}`);
        }
      });

      session.on("error", (error) => {
        console.error("[Session Error]", error);
        addTranscript("System", `Session Error: ${String(error.error)}`);
      });

      session.on("history_updated", (history: RealtimeItem[]) => {
        console.log("[History Updated]", history.length, "items");

        // Process history to extract transcripts
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
                  // Check if we already have this transcript
                  setTranscript((prev) => {
                    const exists = prev.some((t) => t.text === part.text && t.speaker === "You");
                    if (!exists) {
                      return [
                        ...prev,
                        {
                          id: crypto.randomUUID(),
                          speaker: "You",
                          text: part.text ?? "",
                          timestamp: new Date(),
                        },
                      ];
                    }
                    return prev;
                  });
                } else if (part.type === "text" && part.text && role === "assistant") {
                  setTranscript((prev) => {
                    const exists = prev.some((t) => t.text === part.text && t.speaker === "Agent");
                    if (!exists) {
                      return [
                        ...prev,
                        {
                          id: crypto.randomUUID(),
                          speaker: "Agent",
                          text: part.text ?? "",
                          timestamp: new Date(),
                        },
                      ];
                    }
                    return prev;
                  });
                } else if (part.type === "input_audio" && part.transcript) {
                  setTranscript((prev) => {
                    const exists = prev.some(
                      (t) => t.text === part.transcript && t.speaker === "You"
                    );
                    if (!exists) {
                      return [
                        ...prev,
                        {
                          id: crypto.randomUUID(),
                          speaker: "You",
                          text: part.transcript ?? "",
                          timestamp: new Date(),
                        },
                      ];
                    }
                    return prev;
                  });
                } else if (part.type === "audio" && part.transcript && role === "assistant") {
                  setTranscript((prev) => {
                    const exists = prev.some(
                      (t) => t.text === part.transcript && t.speaker === "Agent"
                    );
                    if (!exists) {
                      return [
                        ...prev,
                        {
                          id: crypto.randomUUID(),
                          speaker: "Agent",
                          text: part.transcript ?? "",
                          timestamp: new Date(),
                        },
                      ];
                    }
                    return prev;
                  });
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
      setAudioStatus("Getting session token...");
      const apiBase = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
      const tokenResponse = await fetch(`${apiBase}/api/v1/realtime/token/${selectedAgentId}`);

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
      console.log("[WebRTC] Token session config:", tokenData.session_config);
      setAudioStatus("Connecting via WebRTC...");

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
        setAudioStatus("Connected - Voice active");
        addTranscript("System", "WebRTC connected! Speak to test your agent.");

        // Get tools from token response and system prompt from agent
        const tools = tokenData.tools || [];
        const systemPrompt = tokenData.agent?.system_prompt || selectedAgent.system_prompt || "You are a helpful voice assistant.";

        console.log("[WebRTC] Configuring session with", tools.length, "tools");

        // Send session update with agent config and tools
        const sessionUpdate = {
          type: "session.update",
          session: {
            instructions: systemPrompt,
            voice: "alloy",
            input_audio_transcription: { model: "whisper-1" },
            turn_detection: {
              type: "server_vad",
              threshold: 0.5,
              prefix_padding_ms: 300,
              silence_duration_ms: 500,
            },
            tools: tools,
            tool_choice: tools.length > 0 ? "auto" : "none",
          },
        };
        dataChannel.send(JSON.stringify(sessionUpdate));
        console.log("[WebRTC] Sent session.update with tools:", tools.map((t: { name: string }) => t.name));
      };

      dataChannel.onmessage = async (event) => {
        try {
          const data = JSON.parse(event.data);
          console.log("[WebRTC] Event:", data.type, data);

          // Handle session.updated confirmation
          if (data.type === "session.updated") {
            const toolsConfigured = data.session?.tools?.length || 0;
            console.log("[WebRTC] Session updated - tools configured:", toolsConfigured);
            if (toolsConfigured > 0) {
              addTranscript("System", `Session configured with ${toolsConfigured} tools`);
            }
          }

          // Handle transcription
          if (data.type === "conversation.item.input_audio_transcription.completed") {
            addTranscript("You", data.transcript);
          } else if (data.type === "response.audio_transcript.done") {
            addTranscript("Agent", data.transcript);
          } else if (data.type === "response.function_call_arguments.done") {
            // Handle function/tool call
            const { call_id, name, arguments: argsJson } = data;
            console.log("[WebRTC] Function call:", name, argsJson);
            addTranscript("System", `Calling tool: ${name}`);

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
              console.log("[WebRTC] Sent function_call_output");

              // Trigger response generation
              const responseCreate = { type: "response.create" };
              dataChannel.send(JSON.stringify(responseCreate));
              console.log("[WebRTC] Sent response.create");

              addTranscript("System", `Tool ${name} result: ${toolResult.success ? "Success" : "Failed"}`);
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
            addTranscript("System", `Error: ${data.error?.message || "Unknown error"}`);
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
        setAudioStatus("Disconnected");
      };

      pc.onconnectionstatechange = () => {
        console.log("[WebRTC] Connection state:", pc.connectionState);
        if (pc.connectionState === "disconnected" || pc.connectionState === "failed") {
          cleanup();
          setIsConnected(false);
          setAudioStatus("Disconnected");
        }
      };

      // Store references for cleanup
      sessionRef.current = {
        close: () => {
          dataChannel.close();
          pc.close();
          audioStream.getTracks().forEach((t) => t.stop());
        },
        mute: (muted: boolean) => {
          audioStream.getAudioTracks().forEach((track) => {
            track.enabled = !muted;
          });
        },
      } as unknown as RealtimeSession;

      addTranscript("System", `Tier: ${selectedAgent.pricing_tier}`);
      addTranscript("System", `Tools: ${selectedAgent.enabled_tools.join(", ") || "None"}`);
    } catch (error: unknown) {
      const err = error as Error;
      console.error("[WebRTC] Connection error:", err);
      setAudioStatus("Error");
      addTranscript("System", `Error: ${err.message}`);
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

  const handleMuteToggle = () => {
    if (sessionRef.current) {
      const newMuted = !isMuted;
      sessionRef.current.mute(newMuted);
      setIsMuted(newMuted);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Test Voice Agent</h1>
        <p className="text-muted-foreground">
          Test your voice agents in real-time using OpenAI Agents SDK (WebRTC)
        </p>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Live Testing</CardTitle>
            <CardDescription>Connect to test your agent&apos;s conversation flow</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-4 md:grid-cols-2">
              <div className="space-y-2">
                <Label>Select Agent</Label>
                <Select value={selectedAgentId} onValueChange={setSelectedAgentId}>
                  <SelectTrigger>
                    <SelectValue placeholder="Choose an agent to test" />
                  </SelectTrigger>
                  <SelectContent>
                    {agents.length === 0 ? (
                      <SelectItem value="none" disabled>
                        No agents available - create one first
                      </SelectItem>
                    ) : (
                      agents
                        .filter((agent) => agent.pricing_tier === "premium")
                        .map((agent) => (
                          <SelectItem key={agent.id} value={agent.id}>
                            {agent.name} ({agent.pricing_tier})
                          </SelectItem>
                        ))
                    )}
                  </SelectContent>
                </Select>
                <p className="text-xs text-muted-foreground">
                  Only Premium tier agents support WebRTC
                </p>
              </div>

              <div className="space-y-2">
                <Label>Test Phone Number</Label>
                <Input type="tel" placeholder="+1 (555) 000-0000" disabled={isConnected} />
              </div>
            </div>

            <div className="flex gap-2 pt-4">
              <Button
                onClick={handleConnectClick}
                variant={isConnected ? "destructive" : "default"}
                className="flex-1"
                disabled={!selectedAgentId && !isConnected}
              >
                {isConnected ? (
                  <>
                    <PhoneOff className="mr-2 h-4 w-4" />
                    End Call
                  </>
                ) : (
                  <>
                    <Phone className="mr-2 h-4 w-4" />
                    Start Test Call
                  </>
                )}
              </Button>
              <Button variant="outline" onClick={handleMuteToggle} disabled={!isConnected}>
                {isMuted ? <MicOff className="h-4 w-4" /> : <Mic className="h-4 w-4" />}
              </Button>
            </div>

            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <Label>Call Status</Label>
                <Badge variant={isConnected ? "default" : "secondary"}>{audioStatus}</Badge>
              </div>

              <Card className="bg-muted/50">
                <CardHeader className="pb-3">
                  <CardTitle className="text-sm">Live Transcript</CardTitle>
                </CardHeader>
                <CardContent>
                  <ScrollArea className="h-[300px] w-full rounded-md">
                    {transcript.length === 0 ? (
                      <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
                        Start a test call to see the live transcript
                      </div>
                    ) : (
                      <div className="space-y-3">
                        {transcript.map((item) => (
                          <div key={item.id} className="space-y-1">
                            <div className="flex items-center gap-2">
                              <Badge variant="outline" className="text-xs">
                                {item.speaker}
                              </Badge>
                              <span className="text-xs text-muted-foreground">
                                {item.timestamp.toLocaleTimeString()}
                              </span>
                            </div>
                            <p className="text-sm">{item.text}</p>
                          </div>
                        ))}
                      </div>
                    )}
                  </ScrollArea>
                </CardContent>
              </Card>
            </div>
          </CardContent>
        </Card>

        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Test Metrics</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="flex justify-between text-sm">
                <span className="text-muted-foreground">Connection</span>
                <span className="font-mono">{isConnected ? "WebRTC (SDK)" : "—"}</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-muted-foreground">Transport</span>
                <span className="font-mono">{isConnected ? "OpenAI Agents" : "—"}</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-muted-foreground">Turns</span>
                <span className="font-mono">
                  {transcript.filter((t) => t.speaker !== "System").length}
                </span>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Debug Info</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2 font-mono text-xs">
              <div className="grid grid-cols-2 gap-1">
                <span className="text-muted-foreground">SDK:</span>
                <span>@openai/agents</span>
              </div>
              <div className="grid grid-cols-2 gap-1">
                <span className="text-muted-foreground">Protocol:</span>
                <span>WebRTC</span>
              </div>
              <div className="grid grid-cols-2 gap-1">
                <span className="text-muted-foreground">Audio:</span>
                <span>{isConnected ? (isMuted ? "Muted" : "Active") : "Idle"}</span>
              </div>
              <div className="grid grid-cols-2 gap-1">
                <span className="text-muted-foreground">Status:</span>
                <span>{sessionRef.current?.transport?.status ?? "None"}</span>
              </div>
            </CardContent>
          </Card>

          <Card className="border-green-500/50 bg-green-500/5">
            <CardHeader>
              <CardTitle className="text-sm">OpenAI Agents SDK</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-xs text-muted-foreground">
                Using @openai/agents SDK with WebRTC transport. Audio is handled automatically by
                the SDK for optimal latency and quality.
              </p>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
