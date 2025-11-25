"use client";

import { useEffect } from "react";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import * as z from "zod";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { fetchSettings, updateSettings, type UpdateSettingsRequest } from "@/lib/api/settings";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Separator } from "@/components/ui/separator";

const apiKeysSchema = z.object({
  openaiApiKey: z.string().optional(),
  deepgramApiKey: z.string().optional(),
  elevenLabsApiKey: z.string().optional(),
  telnyxApiKey: z.string().optional(),
  twilioAccountSid: z.string().optional(),
  twilioAuthToken: z.string().optional(),
});

type ApiKeysFormValues = z.infer<typeof apiKeysSchema>;

export default function SettingsPage() {
  const queryClient = useQueryClient();

  // Fetch existing settings
  const { data: settings } = useQuery({
    queryKey: ["settings"],
    queryFn: fetchSettings,
  });

  const form = useForm<ApiKeysFormValues>({
    resolver: zodResolver(apiKeysSchema),
    defaultValues: {
      openaiApiKey: "",
      deepgramApiKey: "",
      elevenLabsApiKey: "",
      telnyxApiKey: "",
      twilioAccountSid: "",
      twilioAuthToken: "",
    },
  });

  // Show placeholders for keys that are set (we don't receive actual values for security)
  useEffect(() => {
    if (settings) {
      // Reset form to show placeholder text for already-set keys
      form.reset({
        openaiApiKey: settings.openai_api_key_set ? "••••••••" : "",
        deepgramApiKey: settings.deepgram_api_key_set ? "••••••••" : "",
        elevenLabsApiKey: settings.elevenlabs_api_key_set ? "••••••••" : "",
        telnyxApiKey: settings.telnyx_api_key_set ? "••••••••" : "",
        twilioAccountSid: settings.twilio_account_sid_set ? "••••••••" : "",
        twilioAuthToken: "",
      });
    }
  }, [settings, form]);

  const updateMutation = useMutation({
    mutationFn: updateSettings,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["settings"] });
      toast.success("Settings saved successfully!");
    },
    onError: (error: Error) => {
      toast.error(`Failed to save settings: ${error.message}`);
    },
  });

  const handleSubmit = (data: ApiKeysFormValues) => {
    // Filter out placeholder values (don't send "••••••••" back to the server)
    const request: UpdateSettingsRequest = {
      openai_api_key: data.openaiApiKey === "••••••••" ? undefined : data.openaiApiKey,
      deepgram_api_key: data.deepgramApiKey === "••••••••" ? undefined : data.deepgramApiKey,
      elevenlabs_api_key: data.elevenLabsApiKey === "••••••••" ? undefined : data.elevenLabsApiKey,
      telnyx_api_key: data.telnyxApiKey === "••••••••" ? undefined : data.telnyxApiKey,
      twilio_account_sid: data.twilioAccountSid === "••••••••" ? undefined : data.twilioAccountSid,
      twilio_auth_token: data.twilioAuthToken,
    };
    updateMutation.mutate(request);
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Settings</h1>
        <p className="text-muted-foreground">Configure your platform settings and API keys</p>
      </div>

      <Tabs defaultValue="api-keys" className="w-full">
        <TabsList>
          <TabsTrigger value="api-keys">API Keys</TabsTrigger>
          <TabsTrigger value="profile">Profile</TabsTrigger>
          <TabsTrigger value="billing">Billing</TabsTrigger>
        </TabsList>

        <TabsContent value="api-keys" className="mt-6 space-y-4">
          <Form {...form}>
            <form
              onSubmit={(e) => {
                e.preventDefault();
                void form.handleSubmit(handleSubmit)();
              }}
              className="space-y-6"
            >
              <Card>
                <CardHeader>
                  <CardTitle>Voice & AI Services</CardTitle>
                  <CardDescription>Configure API keys for voice and AI providers</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <FormField
                    control={form.control}
                    name="openaiApiKey"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>OpenAI API Key</FormLabel>
                        <FormControl>
                          <Input type="password" placeholder="sk-..." {...field} />
                        </FormControl>
                        <FormDescription>
                          Required for GPT-4 and language understanding
                        </FormDescription>
                        <FormMessage />
                      </FormItem>
                    )}
                  />

                  <FormField
                    control={form.control}
                    name="deepgramApiKey"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Deepgram API Key</FormLabel>
                        <FormControl>
                          <Input type="password" placeholder="••••••••" {...field} />
                        </FormControl>
                        <FormDescription>For speech-to-text transcription</FormDescription>
                        <FormMessage />
                      </FormItem>
                    )}
                  />

                  <FormField
                    control={form.control}
                    name="elevenLabsApiKey"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>ElevenLabs API Key</FormLabel>
                        <FormControl>
                          <Input type="password" placeholder="••••••••" {...field} />
                        </FormControl>
                        <FormDescription>
                          For natural text-to-speech voice synthesis
                        </FormDescription>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>Telephony Providers</CardTitle>
                  <CardDescription>Configure phone number providers</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <FormField
                    control={form.control}
                    name="telnyxApiKey"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Telnyx API Key</FormLabel>
                        <FormControl>
                          <Input type="password" placeholder="KEY..." {...field} />
                        </FormControl>
                        <FormDescription>Primary telephony provider (recommended)</FormDescription>
                        <FormMessage />
                      </FormItem>
                    )}
                  />

                  <Separator />

                  <div className="space-y-4">
                    <div className="text-sm font-medium">Twilio (Optional)</div>
                    <FormField
                      control={form.control}
                      name="twilioAccountSid"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>Account SID</FormLabel>
                          <FormControl>
                            <Input type="password" placeholder="AC..." {...field} />
                          </FormControl>
                          <FormMessage />
                        </FormItem>
                      )}
                    />

                    <FormField
                      control={form.control}
                      name="twilioAuthToken"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>Auth Token</FormLabel>
                          <FormControl>
                            <Input type="password" placeholder="••••••••" {...field} />
                          </FormControl>
                          <FormMessage />
                        </FormItem>
                      )}
                    />
                  </div>
                </CardContent>
              </Card>

              <div className="flex justify-end">
                <Button type="submit" disabled={updateMutation.isPending}>
                  {updateMutation.isPending ? "Saving..." : "Save Settings"}
                </Button>
              </div>
            </form>
          </Form>
        </TabsContent>

        <TabsContent value="profile" className="mt-6 space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Profile Settings</CardTitle>
              <CardDescription>Manage your account information</CardDescription>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-muted-foreground">Profile settings coming soon...</p>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="billing" className="mt-6 space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Billing & Usage</CardTitle>
              <CardDescription>View your usage and manage billing</CardDescription>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-muted-foreground">Billing information coming soon...</p>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
