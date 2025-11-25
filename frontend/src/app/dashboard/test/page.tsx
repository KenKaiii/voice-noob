"use client";

/* eslint-disable no-console -- Debug logging is intentional for WebSocket/audio troubleshooting */

import { useState, useRef, useEffect } from "react";
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

export default function TestAgentPage() {
  const [selectedAgentId, setSelectedAgentId] = useState<string>("");
  const [isConnected, setIsConnected] = useState(false);
  const [isMuted, setIsMuted] = useState(false);
  const [transcript, setTranscript] = useState<
    Array<{ id: string; speaker: string; text: string; timestamp: Date }>
  >([]);
  const [audioStatus, setAudioStatus] = useState<string>("Not connected");
  const [isAgentSpeaking, setIsAgentSpeaking] = useState(false);

  const wsRef = useRef<WebSocket | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const processorRef = useRef<ScriptProcessorNode | null>(null);

  // Fetch agents from API
  const { data: agents = [] } = useQuery({
    queryKey: ["agents"],
    queryFn: fetchAgents,
  });

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (processorRef.current) {
        processorRef.current.disconnect();
      }
      if (wsRef.current) {
        wsRef.current.close();
      }
      if (mediaStreamRef.current) {
        mediaStreamRef.current.getTracks().forEach((track) => track.stop());
      }
      if (audioContextRef.current) {
        void audioContextRef.current.close();
      }
    };
  }, []);

  const handleConnect = async () => {
    if (isConnected) {
      // Disconnect
      if (processorRef.current) {
        processorRef.current.disconnect();
        processorRef.current = null;
      }
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
      if (mediaStreamRef.current) {
        mediaStreamRef.current.getTracks().forEach((track) => track.stop());
        mediaStreamRef.current = null;
      }
      if (audioContextRef.current) {
        void audioContextRef.current.close();
        audioContextRef.current = null;
      }
      setIsConnected(false);
      setAudioStatus("Disconnected");
      return;
    }

    if (!selectedAgentId) {
      toast.error("Please select an agent first");
      return;
    }

    const selectedAgent = agents.find((a) => a.id === selectedAgentId);
    if (!selectedAgent) return;

    try {
      // Step 1: Request microphone access
      setAudioStatus("Requesting microphone access...");
      addTranscript("System", "Requesting microphone permission...");

      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      mediaStreamRef.current = stream;
      addTranscript("System", "✓ Microphone access granted");

      // Step 2: Connect WebSocket to backend
      setAudioStatus("Connecting to voice agent...");
      addTranscript("System", `Connecting to ${selectedAgent.name}...`);

      const wsBase = process.env.NEXT_PUBLIC_WS_URL ?? "ws://localhost:8000";
      const ws = new WebSocket(`${wsBase}/ws/realtime/${selectedAgentId}`);
      wsRef.current = ws;

      ws.onopen = () => {
        console.log("[WebSocket] Connected");
        setIsConnected(true);
        setAudioStatus("Connected - Voice active");
        addTranscript("System", "✓ Connected to voice agent");
        addTranscript("System", `Tier: ${selectedAgent.pricing_tier}`);
        addTranscript("System", `Tools: ${selectedAgent.enabled_tools.join(", ")}`);
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          console.log("[WebSocket] Received:", data.type);

          if (data.type === "session.ready") {
            console.log("[Session] Ready - session_id:", data.session_id);
            addTranscript("Agent", "Hello! How can I help you today?");
          } else if (data.type === "input_audio_buffer.speech_started") {
            console.log("[VAD] User started speaking - interrupting agent");
            setIsAgentSpeaking(false);
            // Send truncate command to stop agent's current response
            ws.send(
              JSON.stringify({
                type: "response.cancel",
              })
            );
          } else if (data.type === "conversation.item.input_audio_transcription.completed") {
            addTranscript("You", data.event?.transcript ?? "(audio)");
          } else if (data.type === "response.audio.delta") {
            // Play audio chunk from agent
            const audioData = data.event?.delta;
            if (audioData) {
              void playAudioChunk(audioData);
            }
          } else if (data.type === "response.audio.done") {
            console.log("[Audio] Agent finished speaking");
            setIsAgentSpeaking(false);
          } else if (data.type === "response.audio_transcript.delta") {
            setIsAgentSpeaking(true);
          } else if (data.type === "response.audio_transcript.done") {
            addTranscript("Agent", data.event?.transcript ?? "");
          } else if (data.type === "response.done") {
            console.log("[Response] Done");
            setIsAgentSpeaking(false);
          } else if (data.type === "error") {
            console.error("[Error]", data.error);
            addTranscript("System", `✗ Error: ${data.error}`);
          }
        } catch (e) {
          console.error("[WebSocket] Error parsing message:", e);
        }
      };

      ws.onerror = (error) => {
        console.error("[WebSocket] Error:", error);
        setAudioStatus("Connection error");
        addTranscript("System", "✗ Connection error - check if OPENAI_API_KEY is set in backend");
      };

      ws.onclose = (event) => {
        console.log("[WebSocket] Closed:", event.code, event.reason);
        setIsConnected(false);
        setAudioStatus("Disconnected");
        addTranscript("System", `Call ended (code: ${event.code})`);
      };

      // Step 3: Set up audio capture and streaming
      const audioContext = new AudioContext({ sampleRate: 24000 });
      audioContextRef.current = audioContext;
      const source = audioContext.createMediaStreamSource(stream);

      // Create audio processor to capture and send audio
      const processor = audioContext.createScriptProcessor(4096, 1, 1);
      processorRef.current = processor;

      processor.onaudioprocess = (e) => {
        // Only send audio if connected, not muted, and agent is not speaking
        if (ws.readyState === WebSocket.OPEN && !isMuted && !isAgentSpeaking) {
          const inputData = e.inputBuffer.getChannelData(0);

          // Convert Float32Array to Int16Array (PCM16)
          const pcm16 = new Int16Array(inputData.length);
          for (let i = 0; i < inputData.length; i++) {
            const sample = inputData[i];
            if (sample !== undefined) {
              const s = Math.max(-1, Math.min(1, sample));
              pcm16[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
            }
          }

          // Send as binary data
          ws.send(pcm16.buffer);
        }
      };

      // Connect audio graph: source -> processor -> destination
      source.connect(processor);
      processor.connect(audioContext.destination);

      console.log("[Audio] Microphone active, sample rate:", audioContext.sampleRate);
      addTranscript("System", "🎤 Microphone active - speak to test your agent!");
    } catch (error: unknown) {
      const err = error as Error;
      setAudioStatus("Error");
      addTranscript("System", `✗ Error: ${err.message}`);
      if (err.name === "NotAllowedError") {
        toast.error(
          "Microphone access denied. Please allow microphone access in your browser settings."
        );
      }
    }
  };

  const handleConnectClick = () => {
    void handleConnect();
  };

  const addTranscript = (speaker: string, text: string) => {
    setTranscript((prev) => [
      ...prev,
      {
        id: crypto.randomUUID(),
        speaker,
        text,
        timestamp: new Date(),
      },
    ]);
  };

  const playAudioChunk = async (base64Audio: string) => {
    const audioContext = audioContextRef.current;
    if (!audioContext) return;

    try {
      // Decode base64 to binary
      const binaryString = atob(base64Audio);
      const bytes = new Uint8Array(binaryString.length);
      for (let i = 0; i < binaryString.length; i++) {
        bytes[i] = binaryString.charCodeAt(i);
      }

      // Convert Int16 PCM to Float32 for Web Audio API
      const int16Array = new Int16Array(bytes.buffer);
      const float32Array = new Float32Array(int16Array.length);
      for (let i = 0; i < int16Array.length; i++) {
        const sample = int16Array[i];
        float32Array[i] = sample !== undefined ? sample / 32768.0 : 0;
      }

      // Create audio buffer and play
      const audioBuffer = audioContext.createBuffer(1, float32Array.length, 24000);
      audioBuffer.getChannelData(0).set(float32Array);

      const source = audioContext.createBufferSource();
      source.buffer = audioBuffer;
      source.connect(audioContext.destination);

      // Play immediately - Web Audio API handles queuing internally
      source.start(0);

      console.log("[Audio] Playing chunk:", float32Array.length, "samples");
    } catch (e) {
      console.error("[Audio] Playback error:", e);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Test Voice Agent</h1>
        <p className="text-muted-foreground">
          Test your voice agents in real-time before deployment
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
                      agents.map((agent) => (
                        <SelectItem key={agent.id} value={agent.id}>
                          {agent.name} ({agent.pricing_tier})
                        </SelectItem>
                      ))
                    )}
                  </SelectContent>
                </Select>
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
              <Button
                variant="outline"
                onClick={() => setIsMuted(!isMuted)}
                disabled={!isConnected}
              >
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
                <span className="text-muted-foreground">Latency</span>
                <span className="font-mono">{isConnected ? "~150ms" : "—"}</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-muted-foreground">Duration</span>
                <span className="font-mono">{isConnected ? "00:00" : "—"}</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-muted-foreground">Turns</span>
                <span className="font-mono">{transcript.length}</span>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Debug Info</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2 font-mono text-xs">
              <div className="grid grid-cols-2 gap-1">
                <span className="text-muted-foreground">STT:</span>
                <span>{isConnected ? "Active" : "Idle"}</span>
              </div>
              <div className="grid grid-cols-2 gap-1">
                <span className="text-muted-foreground">TTS:</span>
                <span>{isConnected ? "Active" : "Idle"}</span>
              </div>
              <div className="grid grid-cols-2 gap-1">
                <span className="text-muted-foreground">LLM:</span>
                <span>{isConnected ? "Active" : "Idle"}</span>
              </div>
              <div className="grid grid-cols-2 gap-1">
                <span className="text-muted-foreground">WebSocket:</span>
                <span>{isConnected ? "Connected" : "Disconnected"}</span>
              </div>
            </CardContent>
          </Card>

          <Card className="border-amber-500/50 bg-amber-500/5">
            <CardHeader>
              <CardTitle className="text-sm">Test Mode</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-xs text-muted-foreground">
                This is a testing interface. Calls made here will not be billed and will not appear
                in call history.
              </p>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
