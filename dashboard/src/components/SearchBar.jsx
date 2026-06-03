/**
 * SearchBar.jsx — Multi-modal query input component.
 * Three modes: text (keyboard), voice (mic + MediaRecorder), image (file upload).
 */

import { useState, useRef, useCallback } from 'react'
import {
  KeyboardIcon, MicIcon, StopIcon, ImageIcon,
  SendIcon, SpinnerIcon, UploadIcon, SearchIcon,
} from './Icons'

const MODES = [
  { id: 'text',  label: 'Text',  Icon: KeyboardIcon },
  { id: 'voice', label: 'Voice', Icon: MicIcon      },
  { id: 'image', label: 'Image', Icon: ImageIcon    },
]

export default function SearchBar({ onSearch, loading }) {
  const [mode, setMode]           = useState('text')
  const [query, setQuery]         = useState('')
  const [recording, setRecording] = useState(false)
  const [imageFile, setImageFile] = useState(null)
  const [imagePreview, setImagePreview] = useState(null)
  const [dragOver, setDragOver]   = useState(false)

  const mediaRecorderRef = useRef(null)
  const audioChunksRef   = useRef([])
  const fileInputRef     = useRef(null)

  const handleTextSubmit = (e) => {
    e.preventDefault()
    if (!query.trim() || loading) return
    onSearch({ type: 'text', query: query.trim() })
  }

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
        ? 'audio/webm;codecs=opus'
        : MediaRecorder.isTypeSupported('audio/ogg;codecs=opus')
          ? 'audio/ogg;codecs=opus'
          : ''
      const mr = mimeType ? new MediaRecorder(stream, { mimeType }) : new MediaRecorder(stream)
      audioChunksRef.current = []
      mr.ondataavailable = (e) => audioChunksRef.current.push(e.data)
      mr.onstop = () => {
        const type = mr.mimeType || 'audio/webm'
        const blob = new Blob(audioChunksRef.current, { type })
        stream.getTracks().forEach((t) => t.stop())
        onSearch({ type: 'voice', audioBlob: blob, mimeType: type })
      }
      mr.start()
      mediaRecorderRef.current = mr
      setRecording(true)
    } catch {
      alert('Microphone permission denied.')
    }
  }

  const stopRecording = () => {
    mediaRecorderRef.current?.stop()
    setRecording(false)
  }

  const handleImageFile = useCallback((file) => {
    if (!file || !file.type.startsWith('image/')) return
    setImageFile(file)
    setImagePreview(URL.createObjectURL(file))
  }, [])

  const handleDrop = (e) => {
    e.preventDefault()
    setDragOver(false)
    handleImageFile(e.dataTransfer.files[0])
  }

  const handleImageSubmit = () => {
    if (!imageFile || loading) return
    onSearch({ type: 'image', imageFile })
  }

  const clearImage = () => {
    setImageFile(null)
    setImagePreview(null)
  }

  return (
    <div className="w-full max-w-2xl mx-auto">
      {/* Mode tabs */}
      <div className="flex gap-1 mb-4 bg-slate-50 p-1 rounded-xl border border-slate-200">
        {MODES.map(({ id, label, Icon }) => (
          <button
            key={id}
            onClick={() => { setMode(id); clearImage(); setQuery('') }}
            className={`
              flex-1 flex items-center justify-center gap-2 py-2.5 rounded-lg
              text-sm font-medium transition-all duration-200
              ${mode === id
                ? 'bg-white text-slate-900 shadow-sm border border-slate-200'
                : 'text-slate-500 hover:text-slate-900 hover:bg-white/60'}
            `}
          >
            <Icon className="w-4 h-4" />
            {label}
          </button>
        ))}
      </div>

      {/* Text mode */}
      {mode === 'text' && (
        <form onSubmit={handleTextSubmit} className="relative">
          <div className="flex items-center bg-white border border-slate-300 rounded-xl overflow-hidden
            focus-within:border-blue-600 focus-within:ring-1 focus-within:ring-blue-500/30 transition-all">
            <div className="pl-4 text-slate-400">
              <SearchIcon className="w-5 h-5" />
            </div>
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="What were you reading about machine learning..."
              className="flex-1 bg-transparent px-3 py-4 text-slate-900 placeholder-slate-400
                text-[15px] outline-none"
              autoFocus
            />
            <button
              type="submit"
              disabled={!query.trim() || loading}
              className="m-2 p-2.5 bg-blue-600 hover:bg-blue-700 disabled:bg-slate-100
                disabled:text-slate-400 text-white rounded-lg transition-all duration-150
                disabled:cursor-not-allowed"
            >
              {loading
                ? <SpinnerIcon className="w-4 h-4" />
                : <SendIcon className="w-4 h-4" />}
            </button>
          </div>
        </form>
      )}

      {/* Voice mode */}
      {mode === 'voice' && (
        <div className="flex flex-col items-center py-8 gap-6
          bg-slate-50 border border-slate-200 rounded-xl">
          <p className="text-sm text-slate-500">
            {recording ? 'Recording — click to stop' : 'Click to start recording'}
          </p>

          <div className="relative flex items-center justify-center">
            {recording && (
              <>
                <span className="absolute w-24 h-24 rounded-full bg-red-500/10 animate-pulse-ring" />
                <span className="absolute w-20 h-20 rounded-full bg-red-500/15 animate-pulse-ring"
                  style={{ animationDelay: '0.2s' }} />
              </>
            )}
            <button
              onClick={recording ? stopRecording : startRecording}
              disabled={loading}
              className={`
                relative z-10 w-16 h-16 rounded-full flex items-center justify-center
                transition-all duration-200 shadow-md
                ${recording
                  ? 'bg-red-500 hover:bg-red-600 text-white'
                  : 'bg-blue-600 hover:bg-blue-700 text-white'}
                disabled:opacity-40 disabled:cursor-not-allowed
              `}
            >
              {loading
                ? <SpinnerIcon className="w-6 h-6" />
                : recording
                  ? <StopIcon className="w-6 h-6" />
                  : <MicIcon className="w-6 h-6" />}
            </button>
          </div>

          {recording && (
            <div className="flex gap-1 items-end h-6">
              {Array.from({ length: 5 }).map((_, i) => (
                <div
                  key={i}
                  className="w-1 bg-red-500 rounded-full animate-pulse"
                  style={{
                    height: `${[10, 20, 14, 24, 10][i]}px`,
                    animationDelay: `${i * 0.15}s`,
                  }}
                />
              ))}
            </div>
          )}
        </div>
      )}

      {/* Image mode */}
      {mode === 'image' && (
        <div className="flex flex-col gap-3">
          {!imagePreview ? (
            <div
              onDrop={handleDrop}
              onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
              onDragLeave={() => setDragOver(false)}
              onClick={() => fileInputRef.current?.click()}
              className={`
                flex flex-col items-center justify-center gap-3 py-12 rounded-xl
                border-2 border-dashed cursor-pointer transition-all duration-200
                ${dragOver
                  ? 'border-blue-600 bg-blue-50'
                  : 'border-slate-300 bg-slate-50 hover:border-blue-300 hover:bg-blue-50'}
              `}
            >
              <UploadIcon className="w-8 h-8 text-slate-400" />
              <div className="text-center">
                <p className="text-sm font-medium text-slate-700">
                  Drop an image or click to browse
                </p>
                <p className="text-xs text-slate-400 mt-1">PNG, JPG, WEBP</p>
              </div>
              <input
                ref={fileInputRef}
                type="file"
                accept="image/*"
                className="hidden"
                onChange={(e) => handleImageFile(e.target.files[0])}
              />
            </div>
          ) : (
            <div className="relative rounded-xl overflow-hidden border border-slate-300">
              <img src={imagePreview} alt="Preview" className="w-full h-40 object-cover" />
              <button
                onClick={clearImage}
                className="absolute top-2 right-2 w-7 h-7 bg-white/90 hover:bg-white
                  rounded-lg flex items-center justify-center text-slate-700 hover:text-slate-900
                  text-xs font-bold transition-all shadow-sm"
              >
                ×
              </button>
            </div>
          )}

          {imageFile && (
            <button
              onClick={handleImageSubmit}
              disabled={loading}
              className="w-full py-3.5 bg-blue-600 hover:bg-blue-700 disabled:bg-slate-100
                disabled:text-slate-400 text-white rounded-xl font-medium text-sm
                flex items-center justify-center gap-2 transition-all shadow-sm"
            >
              {loading ? <SpinnerIcon className="w-4 h-4" /> : <SendIcon className="w-4 h-4" />}
              {loading ? 'Searching…' : 'Search with this image'}
            </button>
          )}
        </div>
      )}
    </div>
  )
}
