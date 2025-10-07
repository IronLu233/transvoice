'use client';

import { useState } from 'react';
import FileList from '@/components/FileList';
import Editor from '@/components/Editor';

export default function Home() {
  const [selectedFile, setSelectedFile] = useState<string | null>(null);

  return (
    <div className="flex h-screen" style={{
      background: 'transparent',
      position: 'relative'
    }}>
      <FileList onFileSelect={setSelectedFile} selectedFile={selectedFile} />
      {selectedFile ? (
        <Editor fileId={selectedFile} />
      ) : (
        <div className="flex-1 flex items-center justify-center">
          <div className="text-center p-8 rounded-2xl" style={{
            background: 'var(--card-bg)',
            border: '1px solid var(--card-border)',
            boxShadow: 'var(--shadow-lg)'
          }}>
            <div className="mb-4">
              <div style={{
                width: '80px',
                height: '80px',
                margin: '0 auto',
                background: 'var(--gradient-primary)',
                borderRadius: '50%',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: '2rem',
                boxShadow: 'var(--shadow-glow)'
              }}>
                📝
              </div>
            </div>
            <h2 className="text-3xl font-bold mb-4" style={{
              color: 'var(--text-primary)',
              background: 'var(--gradient-primary)',
              WebkitBackgroundClip: 'text',
              WebkitTextFillColor: 'transparent',
              backgroundClip: 'text'
            }}>
              翻译文件编辑器
            </h2>
            <p style={{
              color: 'var(--text-secondary)',
              fontSize: '1.1rem',
              lineHeight: 1.6
            }}>
              请从左侧列表中选择一个翻译文件开始编辑
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
