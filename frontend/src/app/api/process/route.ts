import { NextRequest, NextResponse } from 'next/server';

// On utilise la même logique d'URL que pour le process
const BACKEND_URL = process.env.API_URL || 'http://localhost:8000';
const TIMEOUT_MS = 5 * 60 * 1000; // 5 minutes


export async function POST(request: NextRequest) {
  console.log("Debug runtime - API_URL:", BACKEND_URL);

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), TIMEOUT_MS);

  try {
    const formData = await request.formData();
    console.log("Tentative d'appel vers:", `${BACKEND_URL}/api/process`);
    const response = await fetch(`${BACKEND_URL}/api/process`, {
      method: 'POST',
      body: formData,
      signal: controller.signal,
    });

    clearTimeout(timeoutId);

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      return NextResponse.json(
        { detail: errorData.detail || `Erreur ${response.status}` },
        { status: response.status }
      );
    }

    // Le backend retourne maintenant du JSON avec le PDF en base64
    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    clearTimeout(timeoutId);

    if (error instanceof Error && error.name === 'AbortError') {
      return NextResponse.json(
        { detail: 'Le traitement a depasse le delai maximum de 5 minutes' },
        { status: 504 }
      );
    }

    return NextResponse.json(
      { detail: error instanceof Error ? error.message : 'Erreur interne' },
      { status: 500 }
    );
  }
}
