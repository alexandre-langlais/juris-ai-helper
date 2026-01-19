'use client';

import { useState } from 'react';
import { FileText, Download, AlertCircle, CheckCircle2, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Progress } from '@/components/ui/progress';
import { FileUpload } from '@/components/file-upload';

type ProcessingStatus = 'idle' | 'uploading' | 'processing' | 'success' | 'error';

interface ProcessingResult {
  blob: Blob;
  filename: string;
  annotationsCount: number;
}

export default function Home() {
  const [pdfFile, setPdfFile] = useState<File | null>(null);
  const [csvFile, setCsvFile] = useState<File | null>(null);
  const [status, setStatus] = useState<ProcessingStatus>('idle');
  const [progress, setProgress] = useState(0);
  const [errorMessage, setErrorMessage] = useState('');
  const [result, setResult] = useState<ProcessingResult | null>(null);

  const canSubmit = pdfFile && csvFile && status === 'idle';

  const handleSubmit = async () => {
    if (!pdfFile || !csvFile) return;

    setStatus('uploading');
    setProgress(10);
    setErrorMessage('');
    setResult(null);

    const formData = new FormData();
    formData.append('pdf', pdfFile);
    formData.append('csv', csvFile);

    try {
      setProgress(30);
      setStatus('processing');

      const response = await fetch('/api/process', {
        method: 'POST',
        body: formData,
      });

      setProgress(80);

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `Erreur ${response.status}`);
      }

      const blob = await response.blob();
      const annotationsCount = parseInt(
        response.headers.get('X-Annotations-Count') || '0',
        10
      );

      const originalName = pdfFile.name.replace(/\.pdf$/i, '');
      const filename = `${originalName}_annote.pdf`;

      setResult({ blob, filename, annotationsCount });
      setProgress(100);
      setStatus('success');
    } catch (error) {
      setStatus('error');
      setErrorMessage(
        error instanceof Error ? error.message : 'Une erreur est survenue'
      );
    }
  };

  const handleDownload = () => {
    if (!result) return;

    const url = URL.createObjectURL(result.blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = result.filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const handleReset = () => {
    setPdfFile(null);
    setCsvFile(null);
    setStatus('idle');
    setProgress(0);
    setErrorMessage('');
    setResult(null);
  };

  return (
    <div className="container mx-auto px-4 py-12 max-w-2xl">
      <div className="text-center mb-8">
        <div className="flex items-center justify-center gap-3 mb-4">
          <FileText className="h-10 w-10 text-primary" />
          <h1 className="text-3xl font-bold">JurisAnnotate AI</h1>
        </div>
        <p className="text-muted-foreground">
          Annotez automatiquement vos contrats PDF avec l&apos;intelligence artificielle
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Annotation de contrat</CardTitle>
          <CardDescription>
            Importez votre contrat PDF et le fichier CSV contenant les sujets et
            commentaires
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          {/* Upload Zone */}
          {status === 'idle' && (
            <>
              <div className="space-y-4">
                <div>
                  <label className="text-sm font-medium mb-2 block">
                    Contrat PDF
                  </label>
                  <FileUpload
                    accept=".pdf"
                    label="Glissez votre PDF ici"
                    description="ou cliquez pour parcourir"
                    file={pdfFile}
                    onFileSelect={setPdfFile}
                  />
                </div>

                <div>
                  <label className="text-sm font-medium mb-2 block">
                    Fichier CSV (sujets et commentaires)
                  </label>
                  <FileUpload
                    accept=".csv"
                    label="Glissez votre CSV ici"
                    description="Colonnes requises: sujet, commentaire"
                    file={csvFile}
                    onFileSelect={setCsvFile}
                  />
                </div>
              </div>

              <Button
                onClick={handleSubmit}
                disabled={!canSubmit}
                className="w-full"
                size="lg"
              >
                Analyser et annoter
              </Button>
            </>
          )}

          {/* Processing State */}
          {(status === 'uploading' || status === 'processing') && (
            <div className="space-y-4 py-8">
              <div className="flex items-center justify-center gap-3">
                <Loader2 className="h-6 w-6 animate-spin text-primary" />
                <span className="text-lg font-medium">
                  {status === 'uploading'
                    ? 'Envoi des fichiers...'
                    : 'Analyse en cours...'}
                </span>
              </div>
              <Progress value={progress} className="h-2" />
              <p className="text-center text-sm text-muted-foreground">
                L&apos;analyse peut prendre plusieurs minutes selon la taille du
                document
              </p>
            </div>
          )}

          {/* Success State */}
          {status === 'success' && result && (
            <div className="space-y-4 py-4">
              <div className="flex items-center justify-center gap-2 text-green-600">
                <CheckCircle2 className="h-6 w-6" />
                <span className="text-lg font-medium">Traitement termine</span>
              </div>
              <p className="text-center text-muted-foreground">
                {result.annotationsCount} annotation
                {result.annotationsCount !== 1 ? 's' : ''} ajoutee
                {result.annotationsCount !== 1 ? 's' : ''} au document
              </p>
              <div className="flex gap-3">
                <Button onClick={handleDownload} className="flex-1" size="lg">
                  <Download className="mr-2 h-4 w-4" />
                  Telecharger le PDF annote
                </Button>
                <Button onClick={handleReset} variant="outline" size="lg">
                  Nouveau
                </Button>
              </div>
            </div>
          )}

          {/* Error State */}
          {status === 'error' && (
            <div className="space-y-4 py-4">
              <div className="flex items-center justify-center gap-2 text-destructive">
                <AlertCircle className="h-6 w-6" />
                <span className="text-lg font-medium">Erreur</span>
              </div>
              <p className="text-center text-muted-foreground">{errorMessage}</p>
              <Button onClick={handleReset} variant="outline" className="w-full">
                Reessayer
              </Button>
            </div>
          )}
        </CardContent>
      </Card>

      <p className="text-center text-xs text-muted-foreground mt-8">
        Tous les documents sont traites localement. Aucune donnee ne quitte votre
        infrastructure.
      </p>
    </div>
  );
}
