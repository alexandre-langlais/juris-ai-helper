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

interface SubjectsPreview {
  valid: boolean;
  subjects_count: number;
  subjects: string[];
  error?: string;
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

  // État pour la progression en temps réel
  const [currentChapter, setCurrentChapter] = useState<string>('');
  const [totalChapters, setTotalChapters] = useState(0);
  const [processedChapters, setProcessedChapters] = useState(0);

  // État pour l'aperçu des sujets (CSV/Excel)
  const [subjectsPreview, setSubjectsPreview] = useState<SubjectsPreview | null>(null);
  const [loadingSubjects, setLoadingSubjects] = useState(false);

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

  // Charger l'aperçu des sujets quand un fichier CSV/Excel est uploadé
  const handleSubjectsFileSelect = useCallback(async (file: File | null) => {
    setCsvFile(file);
    setSubjectsPreview(null);

    if (file) {
      setLoadingSubjects(true);
      try {
        const formData = new FormData();
        formData.append('file', file);

        const response = await fetch('/api/preview-subjects', {
          method: 'POST',
          body: formData,
        });

        if (response.ok) {
          const data = await response.json();
          setSubjectsPreview(data);
        } else {
          const errorData = await response.json().catch(() => ({}));
          setSubjectsPreview({
            valid: false,
            subjects_count: 0,
            subjects: [],
            error: errorData.detail || 'Erreur lors de la validation du fichier',
          });
        }
      } catch (error) {
        console.error('Erreur lors de la validation du fichier:', error);
        setSubjectsPreview({
          valid: false,
          subjects_count: 0,
          subjects: [],
          error: 'Erreur lors de la validation du fichier',
        });
      } finally {
        setLoadingSubjects(false);
      }
    }
  }, []);

  const canSubmit = pdfFile && csvFile && status === 'idle' && !loadingPreview && !loadingSubjects && chapterPreview.length > 0 && subjectsPreview?.valid;

  const handleSubmit = async () => {
    if (!pdfFile || !csvFile) return;

    setStatus('uploading');
    setProgress(5);
    setErrorMessage('');
    setResult(null);
    setExpandedAnalyses(new Set());
    setCurrentChapter('');
    setTotalChapters(0);
    setProcessedChapters(0);

    const formData = new FormData();
    formData.append('pdf', pdfFile);
    formData.append('csv', csvFile);
    if (selectedModel) {
      formData.append('model', selectedModel);
    }

    // Timeout de 10 minutes pour le streaming
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 10 * 60 * 1000);

    try {
      setStatus('processing');

      // Utiliser le endpoint SSE pour la progression en temps réel
      const response = await fetch('/api/process-stream', {
        method: 'POST',
        body: formData,
        signal: controller.signal,
      });

      if (!response.ok) {
        clearTimeout(timeoutId);
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `Erreur ${response.status}`);
      }

      // Lire le stream SSE
      const reader = response.body?.getReader();
      if (!reader) {
        throw new Error('Impossible de lire le stream');
      }

      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6));

              switch (data.type) {
                case 'start':
                  setTotalChapters(data.total_chapters);
                  setProgress(10);
                  break;

                case 'progress':
                  setCurrentChapter(data.chapter_title);
                  // Progress de 10 à 85 pendant l'analyse
                  const progressPercent = 10 + (data.progress_percent * 0.75);
                  setProgress(progressPercent);
                  break;

                case 'chapter_done':
                  setProcessedChapters((prev) => prev + 1);
                  break;

                case 'annotating':
                  setCurrentChapter('');
                  setProgress(90);
                  break;

                case 'complete': {
                  clearTimeout(timeoutId);
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
                  break;
                }

                case 'error':
                  clearTimeout(timeoutId);
                  throw new Error(data.message);
              }
            } catch (parseError) {
              // Ignorer les erreurs de parsing pour les lignes incomplètes
              if (parseError instanceof SyntaxError) continue;
              throw parseError;
            }
          }
        }
      }

      clearTimeout(timeoutId);
    } catch (error) {
      clearTimeout(timeoutId);
      setStatus('error');
      setCurrentChapter('');

      if (error instanceof Error && error.name === 'AbortError') {
        setErrorMessage('Le traitement a depasse le delai maximum de 10 minutes');
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
    setCurrentChapter('');
    setTotalChapters(0);
    setProcessedChapters(0);
    setSubjectsPreview(null);
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
            Importez votre contrat PDF (avec table des matieres) et le fichier de sujets (CSV ou Excel)
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
                    Fichier de sujets (CSV ou Excel)
                  </label>
                  <FileUpload
                    accept=".csv,.xlsx,.xls"
                    label="Glissez votre fichier ici"
                    description="CSV ou Excel - Colonnes requises: sujet, commentaire"
                    file={csvFile}
                    onFileSelect={handleSubjectsFileSelect}
                  />
                </div>

                {/* Aperçu des sujets détectés */}
                {csvFile && (
                  <div className={`border rounded-lg ${subjectsPreview && !subjectsPreview.valid ? 'border-destructive' : ''}`}>
                    <div className="p-3 bg-muted/50 border-b flex items-center gap-2">
                      <FileText className="h-4 w-4" />
                      <span className="font-medium text-sm">
                        Validation du fichier
                      </span>
                      {loadingSubjects && (
                        <Loader2 className="h-4 w-4 animate-spin ml-auto" />
                      )}
                      {!loadingSubjects && subjectsPreview?.valid && (
                        <CheckCircle2 className="h-4 w-4 text-green-600 ml-auto" />
                      )}
                      {!loadingSubjects && subjectsPreview && !subjectsPreview.valid && (
                        <AlertCircle className="h-4 w-4 text-destructive ml-auto" />
                      )}
                    </div>
                    <div className="p-3">
                      {!loadingSubjects && subjectsPreview && !subjectsPreview.valid && (
                        <p className="text-sm text-destructive">
                          {subjectsPreview.error || 'Fichier invalide'}
                        </p>
                      )}
                      {!loadingSubjects && subjectsPreview?.valid && (
                        <>
                          <p className="text-sm text-green-600 font-medium mb-2">
                            {subjectsPreview.subjects_count} sujet{subjectsPreview.subjects_count > 1 ? 's' : ''} detecte{subjectsPreview.subjects_count > 1 ? 's' : ''}
                          </p>
                          {subjectsPreview.subjects.length > 0 && (
                            <div className="space-y-1 max-h-32 overflow-y-auto">
                              {subjectsPreview.subjects.map((subject, index) => (
                                <div
                                  key={index}
                                  className="text-sm py-1 px-2 rounded bg-muted/30 truncate"
                                >
                                  {subject}
                                </div>
                              ))}
                              {subjectsPreview.subjects_count > 10 && (
                                <p className="text-xs text-muted-foreground pt-1">
                                  ... et {subjectsPreview.subjects_count - 10} autre{subjectsPreview.subjects_count - 10 > 1 ? 's' : ''}
                                </p>
                              )}
                            </div>
                          )}
                        </>
                      )}
                    </div>
                  </div>
                )}

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
              {csvFile && subjectsPreview && !subjectsPreview.valid && !loadingSubjects && (
                <p className="text-sm text-destructive text-center">
                  Impossible de lancer l&apos;analyse: fichier de sujets invalide.
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

              {/* Progression détaillée */}
              {status === 'processing' && totalChapters > 0 && (
                <div className="text-center">
                  <p className="text-sm font-medium">
                    Chapitre {processedChapters + 1} / {totalChapters}
                  </p>
                  {currentChapter && (
                    <p className="text-sm text-muted-foreground mt-1 truncate px-4">
                      {currentChapter}
                    </p>
                  )}
                </div>
              )}

              <Progress value={progress} className="h-2" />

              {status === 'processing' && processedChapters > 0 && (
                <p className="text-center text-xs text-muted-foreground">
                  {processedChapters} chapitre{processedChapters > 1 ? 's' : ''} analyse{processedChapters > 1 ? 's' : ''}
                </p>
              )}

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
