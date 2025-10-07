'use client';

import { useState, useEffect, useRef } from 'react';

interface Segment {
  start: number;
  end: number;
  original_text: string;
  translated_text: string;
  original_segments: Array<{
    start: number;
    end: number;
    text: string;
  }>;
}

interface TranslationData {
  total_segments: number;
  segments: Segment[];
}

interface EditorProps {
  fileId: string;
}

export default function Editor({ fileId }: EditorProps) {
  const [data, setData] = useState<TranslationData | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [originalTexts, setOriginalTexts] = useState<string[]>([]);
  const textareaRefs = useRef<(HTMLTextAreaElement | null)[]>([]);

  useEffect(() => {
    if (fileId) {
      loadData();
    }
  }, [fileId]);

  const splitTextBySentence = (text: string) => {
    return text.match(/[^。！？.!?]+[。！？.!?]?/g) || [];
  };

  const joinTextFromSentences = (sentences: string[]) => {
    return sentences.join('');
  };

  const loadData = async () => {
    try {
      setLoading(true);
      const response = await fetch(`/api/file/${fileId}`);
      const result = await response.json();
      const processedData = {
        ...result.data,
        segments: result.data.segments.map((segment: Segment) => ({
          ...segment,
          translated_text: splitTextBySentence(segment.translated_text).join('\n')
        }))
      };
      setData(processedData);
      // Store original texts for reset functionality (split format)
      setOriginalTexts(processedData.segments.map((segment: Segment) => segment.translated_text));
    } catch (error) {
      console.error('Error loading data:', error);
    } finally {
      setLoading(false);
    }
  };

  const saveData = async () => {
    if (!data) return;

    try {
      setSaving(true);
      // Convert back to original format before saving
      const saveData = {
        ...data,
        segments: data.segments.map((segment: Segment) => ({
          ...segment,
          translated_text: joinTextFromSentences(segment.translated_text.split('\n').filter(line => line.trim()))
        }))
      };

      const response = await fetch(`/api/file/${fileId}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(saveData),
      });

      if (response.ok) {
        alert('保存成功！');
      } else {
        alert('保存失败！');
      }
    } catch (error) {
      console.error('Error saving data:', error);
      alert('保存失败！');
    } finally {
      setSaving(false);
    }
  };

  const updateSegmentText = (segmentIndex: number, text: string) => {
    if (data) {
      const newData = { ...data };
      newData.segments[segmentIndex].translated_text = text;
      setData(newData);
    }
  };

  const adjustTextareaHeight = (textarea: HTMLTextAreaElement | null) => {
    if (textarea) {
      textarea.style.height = 'auto';
      textarea.style.height = `${textarea.scrollHeight}px`;
    }
  };

  const handleTextareaChange = (segmentIndex: number, value: string) => {
    updateSegmentText(segmentIndex, value);
    // Adjust height after state update
    setTimeout(() => {
      adjustTextareaHeight(textareaRefs.current[segmentIndex]);
    }, 0);
  };

  const resetSegment = (segmentIndex: number) => {
    if (originalTexts[segmentIndex]) {
      updateSegmentText(segmentIndex, originalTexts[segmentIndex]);
      // Adjust height after reset
      setTimeout(() => {
        adjustTextareaHeight(textareaRefs.current[segmentIndex]);
      }, 0);
    }
  };

  // Adjust all textareas heights when data loads
  useEffect(() => {
    if (data) {
      setTimeout(() => {
        textareaRefs.current.forEach(adjustTextareaHeight);
      }, 100);
    }
  }, [data]);

  const formatTime = (ms: number) => {
    const seconds = Math.floor(ms / 1000);
    const minutes = Math.floor(seconds / 60);
    const hours = Math.floor(minutes / 60);

    if (hours > 0) {
      return `${hours}:${String(minutes % 60).padStart(2, '0')}:${String(seconds % 60).padStart(2, '0')}`;
    }
    return `${minutes}:${String(seconds % 60).padStart(2, '0')}`;
  };

  if (loading) {
    return (
      <div className="flex-1 p-8" style={{ backgroundColor: 'var(--background)' }}>
        <div className="animate-pulse">
          <div className="h-8 rounded w-1/4 mb-6" style={{ backgroundColor: 'var(--text-muted)' }}></div>
          <div className="space-y-4">
            <div className="h-4 rounded" style={{ backgroundColor: 'var(--text-muted)' }}></div>
            <div className="h-4 rounded w-5/6" style={{ backgroundColor: 'var(--text-muted)' }}></div>
            <div className="h-4 rounded w-4/6" style={{ backgroundColor: 'var(--text-muted)' }}></div>
          </div>
        </div>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="flex-1 p-8" style={{ backgroundColor: 'var(--background)' }}>
        <p style={{ color: 'var(--text-secondary)' }}>未找到数据</p>
      </div>
    );
  }

  return (
    <div className="flex-1 p-8 h-screen overflow-y-auto" style={{
      background: 'transparent',
      backdropFilter: 'blur(5px)'
    }}>
      <div className="mb-8">
        <div className="flex justify-between items-center mb-4">
          <div>
            <h1 className="text-3xl font-bold mb-2" style={{
              color: 'var(--text-primary)',
              background: 'var(--gradient-primary)',
              WebkitBackgroundClip: 'text',
              WebkitTextFillColor: 'transparent',
              backgroundClip: 'text'
            }}>
              编辑翻译
            </h1>
            <div className="flex items-center space-x-3">
              <span className="px-3 py-1 rounded-full text-xs font-medium" style={{
                background: 'var(--gradient-primary)',
                color: 'white',
                boxShadow: 'var(--shadow-sm)'
              }}>
                {fileId}
              </span>
              <span className="text-sm" style={{ color: 'var(--text-secondary)' }}>
                总段落数: {data.total_segments}
              </span>
            </div>
          </div>

          <button
            onClick={saveData}
            disabled={saving}
            className={`px-8 py-3 rounded-xl text-white font-medium transition-all duration-300 btn-glow ${
              saving ? 'pulse-animation' : 'hover:scale-105'
            }`}
            style={{
              background: saving
                ? 'linear-gradient(145deg, #6b7280, #9ca3af)'
                : 'var(--gradient-success)',
              boxShadow: saving ? 'var(--shadow-sm)' : 'var(--shadow-md)',
              cursor: saving ? 'not-allowed' : 'pointer',
              opacity: saving ? 0.7 : 1
            }}
            onMouseEnter={(e) => {
              if (!saving) {
                e.currentTarget.style.transform = 'translateY(-2px) scale(1.05)';
                e.currentTarget.style.boxShadow = 'var(--shadow-lg)';
              }
            }}
            onMouseLeave={(e) => {
              if (!saving) {
                e.currentTarget.style.transform = 'translateY(0) scale(1)';
                e.currentTarget.style.boxShadow = 'var(--shadow-md)';
              }
            }}
          >
            {saving ? (
              <div className="flex items-center space-x-2">
                <div style={{
                  width: '16px',
                  height: '16px',
                  border: '2px solid transparent',
                  borderTop: '2px solid white',
                  borderRadius: '50%',
                  animation: 'spin 1s linear infinite'
                }}></div>
                <span>保存中...</span>
              </div>
            ) : (
              <div className="flex items-center space-x-2">
                <span>💾</span>
                <span>保存更改</span>
              </div>
            )}
          </button>
        </div>
      </div>

      <div className="space-y-6">
        {data.segments.map((segment, index) => (
          <div
            key={index}
            className="rounded-xl p-6 card-hover"
            style={{
              background: `linear-gradient(145deg, ${index % 4 === 0 ? '#1e3a5f' : index % 4 === 1 ? '#2b4c7e' : index % 4 === 2 ? '#374151' : '#2d3748'}, ${index % 4 === 0 ? '#2d5a8b' : index % 4 === 1 ? '#3768a8' : index % 4 === 2 ? '#4b5563' : '#374151'})`,
              border: '1px solid var(--card-border)',
              boxShadow: 'var(--shadow-md)',
              position: 'relative',
              overflow: 'hidden'
            }}
          >
            {/* Gradient overlay for depth */}
            <div style={{
              position: 'absolute',
              top: 0,
              left: 0,
              right: 0,
              height: '1px',
              background: 'var(--gradient-primary)',
              opacity: 0.6
            }}></div>

            <div className="mb-4">
              <div className="flex items-center justify-between mb-3">
                <span className="text-xs font-medium px-3 py-1 rounded-full" style={{
                  background: 'var(--gradient-info)',
                  color: 'white',
                  boxShadow: 'var(--shadow-sm)'
                }}>
                  ⏱️ {formatTime(segment.start)} - {formatTime(segment.end)}
                </span>
                <span className="text-xs font-medium" style={{
                  color: 'var(--text-accent)',
                  opacity: 0.8
                }}>
                  段落 {index + 1}
                </span>
              </div>
            </div>

            <div className="mb-4">
              <h3 className="text-base font-semibold mb-3 flex items-center" style={{ color: 'var(--text-primary)' }}>
                <span style={{
                  marginRight: '8px',
                  fontSize: '1.2rem'
                }}>📖</span>
                原文:
              </h3>
              <div
                className="text-base p-4 rounded-lg leading-relaxed"
                style={{
                  color: 'var(--text-secondary)',
                  backgroundColor: 'rgba(15, 15, 35, 0.6)',
                  border: '1px solid rgba(61, 90, 128, 0.3)',
                  backdropFilter: 'blur(5px)'
                }}
              >
                {segment.original_text}
              </div>
            </div>

            <div>
              <h3 className="text-base font-semibold mb-3 flex items-center" style={{ color: 'var(--text-primary)' }}>
                <span style={{
                  marginRight: '8px',
                  fontSize: '1.2rem'
                }}>✏️</span>
                译文:
              </h3>
              <div>
                <textarea
                  ref={(el) => (textareaRefs.current[index] = el)}
                  value={segment.translated_text}
                  onChange={(e) => handleTextareaChange(index, e.target.value)}
                  className="w-full p-4 rounded-lg resize-none overflow-hidden focus:outline-none text-base leading-relaxed transition-all duration-300"
                  style={{
                    backgroundColor: 'rgba(15, 15, 35, 0.8)',
                    border: '1px solid var(--input-border)',
                    color: 'var(--text-primary)',
                    minHeight: '100px',
                    backdropFilter: 'blur(10px)'
                  }}
                  onFocus={(e) => {
                    e.target.style.borderColor = 'var(--accent-primary)';
                    e.target.style.boxShadow = `0 0 0 3px ${getComputedStyle(document.documentElement).getPropertyValue('--accent-primary')}30, 0 0 20px ${getComputedStyle(document.documentElement).getPropertyValue('--accent-primary')}20`;
                    e.target.style.backgroundColor = 'rgba(15, 15, 35, 0.95)';
                  }}
                  onBlur={(e) => {
                    e.target.style.borderColor = 'var(--input-border)';
                    e.target.style.boxShadow = 'none';
                    e.target.style.backgroundColor = 'rgba(15, 15, 35, 0.8)';
                  }}
                />
                <div className="mt-3 flex items-center justify-between">
                  <button
                    onClick={() => resetSegment(index)}
                    className="px-5 py-2 text-white text-sm font-medium rounded-lg transition-all duration-300 btn-glow hover:scale-105"
                    style={{
                      background: 'var(--gradient-secondary)',
                      boxShadow: 'var(--shadow-sm)'
                    }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.transform = 'translateY(-2px) scale(1.05)';
                      e.currentTarget.style.boxShadow = 'var(--shadow-md)';
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.transform = 'translateY(0) scale(1)';
                      e.currentTarget.style.boxShadow = 'var(--shadow-sm)';
                    }}
                  >
                    <div className="flex items-center space-x-2">
                      <span>🔄</span>
                      <span>复位</span>
                    </div>
                  </button>

                  <div className="text-xs" style={{ color: 'var(--text-muted)' }}>
                    {segment.translated_text.split('\n').filter(line => line.trim()).length} 行
                  </div>
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Add spin animation */}
      <style jsx>{`
        @keyframes spin {
          0% { transform: rotate(0deg); }
          100% { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  );
}