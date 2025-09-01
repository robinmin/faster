// Follow Supabase Edge Functions template
import { serve } from "https://deno.land/std@0.168.0/http/server.ts"

console.log("Hello from Functions!")

serve(async (_req) => {
  const data = {
    message: "Hello from Supabase Functions!",
    timestamp: new Date().toISOString(),
  }

  return new Response(
    JSON.stringify(data),
    { headers: { "Content-Type": "application/json" } },
  )
})