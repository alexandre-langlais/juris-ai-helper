import { NextRequest } from 'next/server';

const BACKEND_URL = process.env.API_URL || 'http://localhost:8000';
const TIMEOUT_MS = 10 * 60 * 1000; // 10 minutes pour le streaming

export async function POST(request: NextRequest) {
  console.log("Debug runtime SSE - API_URL:", BACKEND_URL);

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), TIMEOUT_MS);

  try {
    const formData = await request.formData();
    console.log("Tentative d'appel SSE vers:", `${BACKEND_URL}/api/process-stream`);

    const response = await fetch(`${BACKEND_URL}/api/process-stream`, {
      method: 'POST',
      body: formData,
      signal: controller.signal,
    });

    clearTimeout(timeoutId);

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      return new Response(
        JSON.stringify({ detail: errorData.detail || `Erreur ${response.status}` }),
        {
          status: response.status,
          headers: { 'Content-Type': 'application/json' },
        }
      );
    }

    // Streamer la reponse SSE du backend vers le client
    const stream = response.body;
    if (!stream) {
      return new Response(
        JSON.stringify({ detail: 'Pas de stream disponible' }),
        {
          status: 500,
          headers: { 'Content-Type': 'application/json' },
        }
      );
    }

    return new Response(stream, {
      headers: {
        'Content-Type': 'text/event-stream',
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive',
        'X-Accel-Buffering': 'no',
      },
    });
  } catch (error) {
    clearTimeout(timeoutId);

    if (error instanceof Error && error.name === 'AbortError') {
      return new Response(
        JSON.stringify({ detail: 'Le traitement a depasse le delai maximum de 10 minutes' }),
        {
          status: 504,
          headers: { 'Content-Type': 'application/json' },
        }
      );
    }

    return new Response(
      JSON.stringify({ detail: error instanceof Error ? error.message : 'Erreur interne' }),
      {
        status: 500,
        headers: { 'Content-Type': 'application/json' },
      }
    );
  }
}
