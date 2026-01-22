import { NextRequest, NextResponse } from 'next/server';

// On utilise la même logique d'URL que pour le process
const BACKEND_URL = process.env.API_URL || 'http://localhost:8000';

export async function POST(request: NextRequest) {
    try {
        const formData = await request.formData();

        // Proxy vers le backend FastAPI
        const response = await fetch(`${BACKEND_URL}/api/preview`, {
            method: 'POST',
            body: formData,
        });

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            return NextResponse.json(
                { detail: errorData.detail || `Erreur backend: ${response.status}` },
                { status: response.status }
            );
        }

        const data = await response.json();
        return NextResponse.json(data);
    } catch (error) {
        console.error("Erreur sur /api/preview:", error);
        return NextResponse.json(
            { detail: "Impossible de contacter le service d'analyse PDF" },
            { status: 500 }
        );
    }
}