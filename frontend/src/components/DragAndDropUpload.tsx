import React, { useCallback, useState } from 'react'

interface DragAndDropUploadProps {
  onFileSelect: (file: File) => void
  accept?: string
  label?: string
}

export default function DragAndDropUpload({ onFileSelect, accept = "application/pdf", label = "Drag & Drop Resume PDF here or Click to Browse" }: DragAndDropUploadProps) {
  const [isDragOver, setIsDragOver] = useState(false)
  const [fileName, setFileName] = useState<string | null>(null)

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setIsDragOver(true)
  }, [])

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setIsDragOver(false)
  }, [])

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setIsDragOver(false)
    const file = e.dataTransfer.files?.[0]
    if (file) {
      if (accept && !file.type.match(accept.replace('*', '.*'))) {
        alert(`Only ${accept} files are allowed`)
        return
      }
      setFileName(file.name)
      onFileSelect(file)
    }
  }, [accept, onFileSelect])

  const handleChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) {
        setFileName(file.name)
        onFileSelect(file)
    }
  }, [onFileSelect])

  return (
    <div 
      className={`drag-drop-zone ${isDragOver ? 'active' : ''}`}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
      onClick={() => document.getElementById('hidden-file-input')?.click()}
    >
      <input 
        id="hidden-file-input"
        type="file" 
        accept={accept} 
        onChange={handleChange} 
        style={{ display: 'none' }}
      />
      <div>
        <p style={{ fontSize: '1.2rem', marginBottom: '0.5rem' }}>📄</p>
        <p>{fileName ? `Selected: ${fileName}` : label}</p>
      </div>
    </div>
  )
}
