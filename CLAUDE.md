CLAUDE.md - Projet : JurisAnnotate AI
🎯 Vision du Projet

Application web permettant aux juristes d'annoter automatiquement des contrats PDF. L'IA identifie les clauses pertinentes basées sur un sujet défini dans un CSV et insère le commentaire correspondant directement dans le fichier PDF sous forme d'annotation native.
🏗️ Architecture Technique

    Frontend : Next.js (App Router), Tailwind CSS, Shadcn/UI.

    Backend : FastAPI (Python 3.11+).

    IA : Ollama (hébergé sur k3s) utilisant le modèle llama3 ou mistral.

    Traitement PDF : PyMuPDF (fitz) pour l'extraction et l'annotation.

🛠️ Objectifs par Brique
1. Backend (FastAPI) - Dossier /backend

   Endpoint POST /process :

        Accepter un fichier PDF et un fichier CSV.

        Parser le CSV (colonnes: sujet, commentaire).

        Extraire le texte du PDF par blocs (avec leurs coordonnées GPS sur la page).

   Moteur d'IA (Integration Ollama) :

        Envoyer chaque bloc de texte à l'API Ollama locale (http://ollama-service:11434).

        Utiliser un prompt système strict pour matcher le texte avec les sujets du CSV.

   Générateur de PDF :

        Insérer des annotations Sticky Notes via PyMuPDF aux coordonnées du texte matché.

        Retourner le fichier PDF modifié en flux binaire (FileResponse).

2. Frontend (Next.js) - Dossier /frontend

   Interface d'Upload :

        Zone de "Drag & Drop" pour le PDF et le CSV.

        Validation simple des extensions de fichiers.

   Gestion d'État :

        Afficher une barre de progression ou un indicateur d'analyse (le traitement peut être long).

   Visualisation / Téléchargement :

        Proposer le téléchargement du PDF annoté une fois le traitement terminé.

3. Infrastructure (Kubernetes) - Dossier /k8s

   Dockerfiles : Un pour le Front, un pour le Back.

   Manifestes K3s :

        Deployment et Service pour le Backend.

        Deployment et Service pour le Frontend.

        Configuration de l'Ingress pour router /api vers le Backend et le reste vers le Frontend.

📝 Règles de Développement & Conventions

    Priorité à la gratuité : Utiliser exclusivement des bibliothèques Open Source (pas de SaaS payant).

    Confidentialité : Aucun document ne doit quitter le cluster k3s (tout le traitement est local).

    Performance : Préférer PyMuPDF à LangChain pour l'extraction de texte brute pour plus de légèreté.

    Type Safety : Utiliser TypeScript pour le Frontend et Pydantic pour les schémas FastAPI.

🚀 Prochaines Étapes Immédiates

    Initialiser le projet FastAPI avec PyMuPDF et une route de test /health.

    Créer le script de connexion à l'API Ollama.

    Monter l'interface Next.js avec un formulaire d'upload basique vers le backend.