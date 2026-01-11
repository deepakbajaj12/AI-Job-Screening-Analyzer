import React, { useCallback, useState } from 'react'

interface DragAndDropUploadProps {
  onFileSelect: (file: File | null) => void
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

  const handleRemove = (e: React.MouseEvent) => {
    e.stopPropagation()
    setFileName(null)
    onFileSelect(null)
    const input = document.getElementById('hidden-file-input') as HTMLInputElement
    if (input) input.value = ''
  }

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
        className="hidden"
        title="File upload"
      />
      <div>
        <p style={{ fontSize: '1.2rem', marginBottom: '0.5rem' }}>📄</p>
        <p>{fileName ? `Selected: ${fileName}` : label}</p>
        {fileName && (
          <button 
            type="button" 
            onClick={handleRemove}
            style={{ 
              marginTop: '0.5rem', 
              padding: '0.3rem 0.8rem', 
              backgroundColor: '#dc3545', 
              color: 'white', 
              border: 'none', 
              borderRadius: '4px', 
              cursor: 'pointer',
              fontSize: '0.9rem'
            }}
          >
            Remove File
          </button>
        )}
      </div>
    </div>
  )
}
