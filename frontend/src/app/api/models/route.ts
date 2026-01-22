import { NextResponse } from 'next/server';

export async function GET() {
    const BACKEND_URL = process.env.API_URL || 'http://localhost:8000';

    try {
        const response = await fetch(`${BACKEND_URL}/api/models`, {
            cache: 'no-store' // Évite que Next.js ne mette en cache une erreur
        });

        if (!response.ok) throw new Error();

        const data = await response.json();
        return NextResponse.json(data);
    } catch (error) {
        console.error("Erreur proxy models:", error);
        return NextResponse.json({ models: [], default: '' }, { status: 500 });
    }
}