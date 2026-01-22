'use client';

import { useState, useEffect } from 'react';
import {
  FileText,
  Download,
  AlertCircle,
  CheckCircle2,
  Loader2,
  ChevronDown,
  ChevronUp,
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
import { Input } from '@/components/ui/input';
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

export default function Home() {
  const [pdfFile, setPdfFile] = useState<File | null>(null);
  const [csvFile, setCsvFile] = useState<File | null>(null);
  const [status, setStatus] = useState<ProcessingStatus>('idle');
  const [progress, setProgress] = useState(0);
  const [errorMessage, setErrorMessage] = useState('');
  const [result, setResult] = useState<ProcessingResult | null>(null);

  // Nouveaux états pour les options
  const [availableModels, setAvailableModels] = useState<string[]>([]);
  const [selectedModel, setSelectedModel] = useState<string>('');
  const [suggestedFontSize, setSuggestedFontSize] = useState<number | null>(null);
  const [fontSizeInput, setFontSizeInput] = useState<string>('14.0');
  const [analyzingFonts, setAnalyzingFonts] = useState(false);

  // État pour l'affichage des analyses
  const [expandedAnalyses, setExpandedAnalyses] = useState<Set<number>>(new Set());

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

  // Analyser les polices quand un PDF est uploadé
  const handlePdfSelect = async (file: File | null) => {
    setPdfFile(file);
    setSuggestedFontSize(null);

    if (file) {
      setAnalyzingFonts(true);
      try {
        const formData = new FormData();
        formData.append('pdf', file);

        const response = await fetch('/api/analyze-fonts', {
          method: 'POST',
          body: formData,
        });

        if (response.ok) {
          const data = await response.json();
          const suggested = data.suggested_title_size || 14.0;
          setSuggestedFontSize(suggested);
          setFontSizeInput(suggested.toString());
        }
      } catch (error) {
        console.error('Erreur lors de l\'analyse des polices:', error);
      } finally {
        setAnalyzingFonts(false);
      }
    }
  };

  const canSubmit = pdfFile && csvFile && status === 'idle' && !analyzingFonts;

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
    formData.append('min_title_font_size', fontSizeInput);
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
    setSuggestedFontSize(null);
    setFontSizeInput('14.0');
    setExpandedAnalyses(new Set());
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
                    onFileSelect={handlePdfSelect}
                  />
                  {analyzingFonts && (
                    <div className="flex items-center gap-2 mt-2 text-sm text-muted-foreground">
                      <Loader2 className="h-4 w-4 animate-spin" />
                      Analyse des polices en cours...
                    </div>
                  )}
                  {suggestedFontSize !== null && !analyzingFonts && (
                    <p className="text-sm text-muted-foreground mt-2">
                      Taille de police suggérée pour les titres: {suggestedFontSize}
                    </p>
                  )}
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

                {/* Options avancées */}
                <div className="grid grid-cols-2 gap-4 pt-4 border-t">
                  <div>
                    <label className="text-sm font-medium mb-2 block">
                      Taille de police min. des titres
                    </label>
                    <Input
                      type="number"
                      step="0.5"
                      min="6"
                      max="72"
                      value={fontSizeInput}
                      onChange={(e) => setFontSizeInput(e.target.value)}
                      placeholder="14.0"
                    />
                  </div>

                  <div>
                    <label className="text-sm font-medium mb-2 block">
                      Modèle LLM
                    </label>
                    <Select value={selectedModel} onValueChange={setSelectedModel}>
                      <SelectTrigger>
                        <SelectValue placeholder="Sélectionner un modèle" />
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
                                <span className="font-medium">Sujet matché:</span>{' '}
                                {analysis.matched_subject}
                              </p>
                            )}
                            {analysis.matched && analysis.comment_added && (
                              <p>
                                <span className="font-medium">Commentaire ajouté:</span>{' '}
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
