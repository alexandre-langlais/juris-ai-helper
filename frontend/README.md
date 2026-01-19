# JurisAnnotate Frontend

Interface web Next.js pour l'annotation automatique de contrats PDF par IA.

## Prerequis

- Node.js 20+
- npm ou yarn

## Installation

```bash
cd frontend

# Installer les dependances
npm install
```

## Lancement

### Mode developpement

```bash
npm run dev
```

L'application sera accessible sur [http://localhost:3000](http://localhost:3000).

### Mode production

```bash
# Build
npm run build

# Lancement
npm start
```

## Configuration

Copiez le fichier `.env.example` vers `.env.local` et ajustez les valeurs:

```bash
cp .env.example .env.local
```

Variables disponibles:

| Variable | Description | Defaut |
|----------|-------------|--------|
| `NEXT_PUBLIC_API_URL` | URL du backend FastAPI | `http://localhost:8000` |

## Structure du projet

```
frontend/
├── src/
│   ├── app/
│   │   ├── globals.css      # Styles Tailwind
│   │   ├── layout.tsx       # Layout principal
│   │   └── page.tsx         # Page d'upload
│   ├── components/
│   │   ├── file-upload.tsx  # Composant Drag & Drop
│   │   └── ui/              # Composants Shadcn/UI
│   └── lib/
│       └── utils.ts         # Utilitaires
├── public/
├── tailwind.config.ts
└── package.json
```

## Fonctionnalites

- Zone Drag & Drop pour fichiers PDF et CSV
- Validation des extensions de fichiers
- Barre de progression pendant le traitement
- Telechargement du PDF annote
- Gestion des erreurs avec messages explicites

## Technologies utilisees

- [Next.js 14](https://nextjs.org/) - Framework React
- [Tailwind CSS](https://tailwindcss.com/) - Styles utilitaires
- [Shadcn/UI](https://ui.shadcn.com/) - Composants UI
- [Lucide React](https://lucide.dev/) - Icones

## Docker

```bash
docker build -t juris-frontend .
docker run -p 3000:3000 juris-frontend
```

## Developpement

### Linter

```bash
npm run lint
```

### Ajouter un composant Shadcn/UI

Les composants UI sont dans `src/components/ui/`. Pour en ajouter manuellement, consultez [la documentation Shadcn](https://ui.shadcn.com/docs/components).
