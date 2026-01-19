'use client';

import { useCallback, useState } from 'react';
import { Upload, File, X } from 'lucide-react';
import { cn } from '@/lib/utils';

interface FileUploadProps {
  accept: string;
  label: string;
  description: string;
  file: File | null;
  onFileSelect: (file: File | null) => void;
}

export function FileUpload({
  accept,
  label,
  description,
  file,
  onFileSelect,
}: FileUploadProps) {
  const [isDragging, setIsDragging] = useState(false);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setIsDragging(false);

      const droppedFile = e.dataTransfer.files[0];
      if (droppedFile) {
        const extension = droppedFile.name.split('.').pop()?.toLowerCase();
        const acceptedExtensions = accept
          .split(',')
          .map((ext) => ext.trim().replace('.', '').toLowerCase());

        if (extension && acceptedExtensions.includes(extension)) {
          onFileSelect(droppedFile);
        }
      }
    },
    [accept, onFileSelect]
  );

  const handleFileInput = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const selectedFile = e.target.files?.[0];
      if (selectedFile) {
        onFileSelect(selectedFile);
      }
    },
    [onFileSelect]
  );

  const handleRemove = useCallback(() => {
    onFileSelect(null);
  }, [onFileSelect]);

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  if (file) {
    return (
      <div className="relative rounded-lg border bg-muted/50 p-4">
        <div className="flex items-center gap-3">
          <File className="h-8 w-8 text-primary" />
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium truncate">{file.name}</p>
            <p className="text-xs text-muted-foreground">
              {formatFileSize(file.size)}
            </p>
          </div>
          <button
            type="button"
            onClick={handleRemove}
            className="p-1 rounded-full hover:bg-destructive/10 text-destructive"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      </div>
    );
  }

  return (
    <div
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
      className={cn(
        'relative rounded-lg border-2 border-dashed p-6 transition-colors',
        isDragging
          ? 'border-primary bg-primary/5'
          : 'border-muted-foreground/25 hover:border-primary/50'
      )}
    >
      <input
        type="file"
        accept={accept}
        onChange={handleFileInput}
        className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
      />
      <div className="flex flex-col items-center text-center">
        <Upload
          className={cn(
            'h-10 w-10 mb-3',
            isDragging ? 'text-primary' : 'text-muted-foreground'
          )}
        />
        <p className="text-sm font-medium">{label}</p>
        <p className="text-xs text-muted-foreground mt-1">{description}</p>
      </div>
    </div>
  );
}
