'use client';

import { useState, useEffect } from 'react';

interface File {
  id: string;
  name: string;
  path: string;
}

interface FileListProps {
  onFileSelect: (fileId: string) => void;
  selectedFile?: string;
}

export default function FileList({ onFileSelect, selectedFile }: FileListProps) {
  const [files, setFiles] = useState<File[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchFiles();
  }, []);

  const fetchFiles = async () => {
    try {
      const response = await fetch('/api/files');
      const data = await response.json();
      setFiles(data.files || []);
    } catch (error) {
      console.error('Error fetching files:', error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="p-4 border-r w-80" style={{
        background: 'var(--card-bg-solid)',
        borderColor: 'var(--card-border)',
        backdropFilter: 'blur(10px)',
        backgroundColor: 'rgba(30, 58, 95, 0.8)'
      }}>
        <div className="mb-6">
          <div className="h-6 rounded w-32 mb-2 pulse-animation" style={{
            background: 'var(--gradient-primary)',
            backgroundSize: '200% 100%',
            animation: 'gradientShift 2s ease infinite'
          }}></div>
          <div className="h-2 rounded" style={{
            background: 'var(--gradient-primary)',
            width: '60%'
          }}></div>
        </div>
        <div className="space-y-3">
          {[1, 2, 3].map((i) => (
            <div key={i} className="p-4 rounded-xl" style={{
              background: `linear-gradient(145deg, ${i % 3 === 0 ? '#2d3748' : i % 3 === 1 ? '#2b4c7e' : '#1e3a5f'}, ${i % 3 === 0 ? '#374151' : i % 3 === 1 ? '#3768a8' : '#2d5a8b'})`,
              border: '1px solid var(--card-border)'
            }}>
              <div className="flex items-start space-x-3">
                <div className="w-6 h-6 rounded pulse-animation" style={{
                  background: 'var(--gradient-primary)',
                  opacity: 0.6
                }}></div>
                <div className="flex-1">
                  <div className="h-3 rounded mb-2 pulse-animation" style={{
                    background: 'var(--text-muted)',
                    width: '80%'
                  }}></div>
                  <div className="h-2 rounded pulse-animation" style={{
                    background: 'var(--text-muted)',
                    width: '60%'
                  }}></div>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="p-4 border-r w-80 h-screen overflow-y-auto" style={{
      background: 'var(--card-bg-solid)',
      borderColor: 'var(--card-border)',
      backdropFilter: 'blur(10px)',
      backgroundColor: 'rgba(30, 58, 95, 0.8)'
    }}>
      <div className="mb-6">
        <h2 className="text-xl font-bold mb-2" style={{
          color: 'var(--text-primary)',
          background: 'var(--gradient-primary)',
          WebkitBackgroundClip: 'text',
          WebkitTextFillColor: 'transparent',
          backgroundClip: 'text'
        }}>
          翻译文件列表
        </h2>
        <div style={{
          height: '2px',
          background: 'var(--gradient-primary)',
          borderRadius: '1px'
        }}></div>
      </div>

      {files.length === 0 ? (
        <div className="text-center p-6 rounded-lg" style={{
          background: 'var(--input-bg)',
          border: '1px solid var(--input-border)'
        }}>
          <div style={{
            fontSize: '2rem',
            marginBottom: '1rem',
            opacity: 0.6
          }}>
            📁
          </div>
          <p style={{ color: 'var(--text-secondary)' }}>未找到翻译文件</p>
        </div>
      ) : (
        <ul className="space-y-3">
          {files.map((file, index) => (
            <li key={file.id}>
              <button
                onClick={() => onFileSelect(file.id)}
                className={`w-full text-left p-4 rounded-xl transition-all duration-300 border card-hover ${
                  selectedFile === file.id
                    ? 'btn-glow'
                    : 'hover:scale-105'
                }`}
                style={{
                  background: selectedFile === file.id
                    ? 'var(--gradient-primary)'
                    : `linear-gradient(145deg, ${index % 3 === 0 ? '#2d3748' : index % 3 === 1 ? '#2b4c7e' : '#1e3a5f'}, ${index % 3 === 0 ? '#374151' : index % 3 === 1 ? '#3768a8' : '#2d5a8b'})`,
                  borderColor: selectedFile === file.id
                    ? 'transparent'
                    : `var(--card-border)`,
                  color: selectedFile === file.id ? 'white' : 'var(--text-primary)',
                  boxShadow: selectedFile === file.id
                    ? 'var(--shadow-glow)'
                    : 'var(--shadow-sm)'
                }}
              >
                <div className="flex items-start space-x-3">
                  <div style={{
                    fontSize: '1.2rem',
                    marginTop: '2px',
                    opacity: selectedFile === file.id ? 1 : 0.7
                  }}>
                    📄
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="font-medium text-sm truncate mb-1" title={file.name}>
                      {file.name}
                    </div>
                    <div className="text-xs" style={{
                      color: selectedFile === file.id ? 'rgba(255,255,255,0.8)' : 'var(--text-secondary)',
                      opacity: selectedFile === file.id ? 0.9 : 0.7
                    }}>
                      ID: {file.id}
                    </div>
                  </div>
                  {selectedFile === file.id && (
                    <div style={{
                      fontSize: '0.8rem',
                      color: 'rgba(255,255,255,0.9)'
                    }}>
                      ✓
                    </div>
                  )}
                </div>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}