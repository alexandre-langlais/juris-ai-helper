'use client';

import { useState, useEffect, useCallback } from 'react';
import {
  FileText,
  Download,
  AlertCircle,
  CheckCircle2,
  Loader2,
  ChevronDown,
  ChevronUp,
  BookOpen,
} from 'lucide-react';
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';

type ProcessingStatus = 'idle' | 'uploading' | 'processing' | 'success' | 'error';

interface ChapterAnalysis {
  chapter_title: string;
  chapter_pages: string;
  matched: boolean;
  matched_subject?: string;
  comment_added?: string;
  explanation: string;
}

interface ProcessingResult {
  pdfBase64: string;
  filename: string;
  analyses: ChapterAnalysis[];
  totalChapters: number;
  matchedChapters: number;
}

interface ChapterPreview {
  title: string;
  page: number;
}

export default function Home() {
  const [pdfFile, setPdfFile] = useState<File | null>(null);
  const [csvFile, setCsvFile] = useState<File | null>(null);
  const [status, setStatus] = useState<ProcessingStatus>('idle');
  const [progress, setProgress] = useState(0);
  const [errorMessage, setErrorMessage] = useState('');
  const [result, setResult] = useState<ProcessingResult | null>(null);

  // États pour les options
  const [availableModels, setAvailableModels] = useState<string[]>([]);
  const [selectedModel, setSelectedModel] = useState<string>('');

  // État pour l'affichage des analyses
  const [expandedAnalyses, setExpandedAnalyses] = useState<Set<number>>(new Set());

  // État pour l'aperçu des chapitres (table des matières)
  const [chapterPreview, setChapterPreview] = useState<ChapterPreview[]>([]);
  const [loadingPreview, setLoadingPreview] = useState(false);

  // Charger les modèles disponibles au démarrage
  useEffect(() => {
    const fetchModels = async () => {
      try {
        const response = await fetch('/api/models');
        if (response.ok) {
          const data = await response.json();
          setAvailableModels(data.models || []);
          setSelectedModel(data.default || data.models?.[0] || '');
        }
      } catch (error) {
        console.error('Erreur lors du chargement des modèles:', error);
      }
    };
    fetchModels();
  }, []);

  // Charger l'aperçu des chapitres quand un PDF est uploadé
  const handlePdfSelect = useCallback(async (file: File | null) => {
    setPdfFile(file);
    setChapterPreview([]);

    if (file) {
      setLoadingPreview(true);
      try {
        const formData = new FormData();
        formData.append('pdf', file);

        const response = await fetch('/api/preview', {
          method: 'POST',
          body: formData,
        });

        if (response.ok) {
          const data = await response.json();
          setChapterPreview(data.chapters || []);
        }
      } catch (error) {
        console.error('Erreur lors du chargement de l\'aperçu:', error);
      } finally {
        setLoadingPreview(false);
      }
    }
  }, []);

  const canSubmit = pdfFile && csvFile && status === 'idle' && !loadingPreview && chapterPreview.length > 0;

  const handleSubmit = async () => {
    if (!pdfFile || !csvFile) return;

    setStatus('uploading');
    setProgress(10);
    setErrorMessage('');
    setResult(null);
    setExpandedAnalyses(new Set());

    const formData = new FormData();
    formData.append('pdf', pdfFile);
    formData.append('csv', csvFile);
    if (selectedModel) {
      formData.append('model', selectedModel);
    }

    // Timeout de 5 minutes
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 5 * 60 * 1000);

    try {
      setProgress(30);
      setStatus('processing');

      const response = await fetch('/api/process', {
        method: 'POST',
        body: formData,
        signal: controller.signal,
      });

      clearTimeout(timeoutId);
      setProgress(80);

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `Erreur ${response.status}`);
      }

      const data = await response.json();

      const originalName = pdfFile.name.replace(/\.pdf$/i, '');
      const filename = data.pdf_filename || `${originalName}_annote.pdf`;

      setResult({
        pdfBase64: data.pdf_base64,
        filename,
        analyses: data.analyses || [],
        totalChapters: data.total_chapters || 0,
        matchedChapters: data.matched_chapters || 0,
      });
      setProgress(100);
      setStatus('success');
    } catch (error) {
      clearTimeout(timeoutId);
      setStatus('error');

      if (error instanceof Error && error.name === 'AbortError') {
        setErrorMessage('Le traitement a depasse le delai maximum de 5 minutes');
      } else {
        setErrorMessage(
          error instanceof Error ? error.message : 'Une erreur est survenue'
        );
      }
    }
  };

  const handleDownload = () => {
    if (!result) return;

    // Convertir base64 en blob
    const byteCharacters = atob(result.pdfBase64);
    const byteNumbers = new Array(byteCharacters.length);
    for (let i = 0; i < byteCharacters.length; i++) {
      byteNumbers[i] = byteCharacters.charCodeAt(i);
    }
    const byteArray = new Uint8Array(byteNumbers);
    const blob = new Blob([byteArray], { type: 'application/pdf' });

    const url = URL.createObjectURL(blob);
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
    setExpandedAnalyses(new Set());
    setChapterPreview([]);
  };

  const toggleAnalysis = (index: number) => {
    setExpandedAnalyses((prev) => {
      const next = new Set(prev);
      if (next.has(index)) {
        next.delete(index);
      } else {
        next.add(index);
      }
      return next;
    });
  };

  return (
    <div className="container mx-auto px-4 py-12 max-w-3xl">
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
            Importez votre contrat PDF (avec table des matieres) et le fichier CSV contenant les sujets et
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
                    onFileSelect={handlePdfSelect}
                  />
                </div>

                {/* Aperçu des chapitres détectés via table des matières */}
                {pdfFile && (
                  <div className="border rounded-lg">
                    <div className="p-3 bg-muted/50 border-b flex items-center gap-2">
                      <BookOpen className="h-4 w-4" />
                      <span className="font-medium text-sm">
                        Table des matieres detectee
                      </span>
                      {loadingPreview && (
                        <Loader2 className="h-4 w-4 animate-spin ml-auto" />
                      )}
                    </div>
                    <div className="p-3">
                      {!loadingPreview && chapterPreview.length === 0 && (
                        <p className="text-sm text-muted-foreground text-center py-2">
                          Aucune table des matieres detectee dans ce PDF.
                          Assurez-vous que le document contient un sommaire.
                        </p>
                      )}
                      {!loadingPreview && chapterPreview.length > 0 && (
                        <div className="space-y-1 max-h-48 overflow-y-auto">
                          {chapterPreview.map((chapter, index) => (
                            <div
                              key={index}
                              className="flex items-center justify-between text-sm py-1 px-2 rounded hover:bg-muted/50"
                            >
                              <span className="truncate flex-1 mr-2">
                                {chapter.title}
                              </span>
                              <span className="text-muted-foreground text-xs whitespace-nowrap">
                                p. {chapter.page}
                              </span>
                            </div>
                          ))}
                        </div>
                      )}
                      {!loadingPreview && chapterPreview.length > 0 && (
                        <p className="text-xs text-muted-foreground mt-2 pt-2 border-t">
                          {chapterPreview.length} chapitre{chapterPreview.length > 1 ? 's' : ''} detecte{chapterPreview.length > 1 ? 's' : ''}
                        </p>
                      )}
                    </div>
                  </div>
                )}

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

                {/* Sélecteur de modèle LLM */}
                {availableModels.length > 0 && (
                  <div className="pt-4 border-t">
                    <label className="text-sm font-medium mb-2 block">
                      Modele LLM
                    </label>
                    <Select value={selectedModel} onValueChange={setSelectedModel}>
                      <SelectTrigger>
                        <SelectValue placeholder="Selectionner un modele" />
                      </SelectTrigger>
                      <SelectContent>
                        {availableModels.map((model) => (
                          <SelectItem key={model} value={model}>
                            {model}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                )}
              </div>

              <Button
                onClick={handleSubmit}
                disabled={!canSubmit}
                className="w-full"
                size="lg"
              >
                Analyser et annoter
              </Button>

              {pdfFile && chapterPreview.length === 0 && !loadingPreview && (
                <p className="text-sm text-destructive text-center">
                  Impossible de lancer l&apos;analyse: aucune table des matieres detectee.
                </p>
              )}
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
            <div className="space-y-6 py-4">
              <div className="flex items-center justify-center gap-2 text-green-600">
                <CheckCircle2 className="h-6 w-6" />
                <span className="text-lg font-medium">Traitement termine</span>
              </div>
              <p className="text-center text-muted-foreground">
                {result.matchedChapters} correspondance
                {result.matchedChapters !== 1 ? 's' : ''} trouvee
                {result.matchedChapters !== 1 ? 's' : ''} sur {result.totalChapters} chapitre
                {result.totalChapters !== 1 ? 's' : ''}
              </p>

              {/* Analyses détaillées */}
              {result.analyses.length > 0 && (
                <div className="border rounded-lg">
                  <div className="p-3 bg-muted/50 border-b font-medium">
                    Analyses detaillees par chapitre
                  </div>
                  <div className="divide-y">
                    {result.analyses.map((analysis, index) => (
                      <div key={index} className="p-3">
                        <button
                          onClick={() => toggleAnalysis(index)}
                          className="w-full flex items-center justify-between text-left"
                        >
                          <div className="flex items-center gap-2">
                            <span
                              className={`px-2 py-0.5 text-xs rounded ${
                                analysis.matched
                                  ? 'bg-green-100 text-green-800'
                                  : 'bg-gray-100 text-gray-600'
                              }`}
                            >
                              {analysis.matched ? 'MATCH' : '—'}
                            </span>
                            <span className="font-medium">
                              {analysis.chapter_title}
                            </span>
                            <span className="text-sm text-muted-foreground">
                              (p. {analysis.chapter_pages})
                            </span>
                          </div>
                          {expandedAnalyses.has(index) ? (
                            <ChevronUp className="h-4 w-4 text-muted-foreground" />
                          ) : (
                            <ChevronDown className="h-4 w-4 text-muted-foreground" />
                          )}
                        </button>

                        {expandedAnalyses.has(index) && (
                          <div className="mt-3 pl-4 space-y-2 text-sm">
                            {analysis.matched && analysis.matched_subject && (
                              <p>
                                <span className="font-medium">Sujet matche:</span>{' '}
                                {analysis.matched_subject}
                              </p>
                            )}
                            {analysis.matched && analysis.comment_added && (
                              <p>
                                <span className="font-medium">Commentaire ajoute:</span>{' '}
                                {analysis.comment_added}
                              </p>
                            )}
                            <div>
                              <span className="font-medium">Explication du LLM:</span>
                              <p className="mt-1 text-muted-foreground whitespace-pre-wrap">
                                {analysis.explanation}
                              </p>
                            </div>
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}

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
