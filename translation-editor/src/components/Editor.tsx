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
  const [error, setError] = useState<string | null>(null);
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' | 'warning' } | null>(null);
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

      // Check for invalid segments in the original data
      const invalidSegments = result.data.segments.filter((seg: Segment) => seg.start > seg.end);
      if (invalidSegments.length > 0) {
        console.error('Invalid segments found in original data:', invalidSegments);
        showToast(`警告：原始数据中发现 ${invalidSegments.length} 个时间戳错误的段落（start > end）！`, 'warning');
      }

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
        showToast('保存成功！', 'success');
      } else {
        showToast('保存失败！', 'error');
      }
    } catch (error) {
      console.error('Error saving data:', error);
      showToast('保存失败！', 'error');
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
    // Adjust height after state update, but prevent unwanted scrolling
    setTimeout(() => {
      const textarea = textareaRefs.current[segmentIndex];
      if (textarea) {
        // Store current scroll position
        const scrollY = window.scrollY;
        const rect = textarea.getBoundingClientRect();
        const isInViewport = rect.top >= 0 && rect.bottom <= window.innerHeight;

        adjustTextareaHeight(textarea);

        // Only restore scroll position if the textarea was in viewport
        // and the height change would cause unwanted scrolling
        if (isInViewport) {
          window.scrollTo(0, scrollY);
        }
      }
    }, 0);
  };

  const resetSegment = (segmentIndex: number) => {
    if (originalTexts[segmentIndex]) {
      updateSegmentText(segmentIndex, originalTexts[segmentIndex]);
      // Adjust height after reset, but prevent unwanted scrolling
      setTimeout(() => {
        const textarea = textareaRefs.current[segmentIndex];
        if (textarea) {
          // Store current scroll position
          const scrollY = window.scrollY;
          const rect = textarea.getBoundingClientRect();
          const isInViewport = rect.top >= 0 && rect.bottom <= window.innerHeight;

          adjustTextareaHeight(textarea);

          // Only restore scroll position if the textarea was in viewport
          if (isInViewport) {
            window.scrollTo(0, scrollY);
          }
        }
      }, 0);
    }
  };

  const deleteSegment = (segmentIndex: number) => {
    if (data && data.segments.length > 1) {
      const newData = { ...data };
      newData.segments = newData.segments.filter((_, index) => index !== segmentIndex);
      newData.total_segments = newData.segments.length;
      setData(newData);

      // Also remove from originalTexts
      const newOriginalTexts = [...originalTexts];
      newOriginalTexts.splice(segmentIndex, 1);
      setOriginalTexts(newOriginalTexts);

      // Update textarea refs
      textareaRefs.current = textareaRefs.current.filter((_, index) => index !== segmentIndex);
    }
  };

  const mergeWithSegment = (currentIndex: number, targetIndex: number) => {
    if (!data || targetIndex < 0 || targetIndex >= data.segments.length) {
      return;
    }

    const currentSegment = data.segments[currentIndex];
    const targetSegment = data.segments[targetIndex];

    // Determine the new start and end times
    const newStart = Math.min(currentSegment.start, targetSegment.start);
    const newEnd = Math.max(currentSegment.end, targetSegment.end);

    // Merge the translated texts
    const currentText = currentSegment.translated_text;
    const targetText = targetSegment.translated_text;
    const mergedText = currentIndex < targetIndex
      ? `${currentText}\n${targetText}`
      : `${targetText}\n${currentText}`;

    // Merge original texts
    const currentOriginalText = currentSegment.original_text;
    const targetOriginalText = targetSegment.original_text;
    const mergedOriginalText = currentIndex < targetIndex
      ? `${currentOriginalText} ${targetOriginalText}`
      : `${targetOriginalText} ${currentOriginalText}`;

    // Merge original_segments arrays
    const mergedOriginalSegments = currentIndex < targetIndex
      ? [...currentSegment.original_segments, ...targetSegment.original_segments]
      : [...targetSegment.original_segments, ...currentSegment.original_segments];

    // Create the merged segment
    const mergedSegment: Segment = {
      start: newStart,
      end: newEnd,
      original_text: mergedOriginalText,
      translated_text: mergedText,
      original_segments: mergedOriginalSegments
    };

    // Create new segments array
    const newSegments = [...data.segments];

    // Remove both segments and add the merged one
    const indicesToRemove = [currentIndex, targetIndex].sort((a, b) => b - a); // Sort descending to remove correctly
    indicesToRemove.forEach(index => {
      newSegments.splice(index, 1);
    });

    // Insert merged segment at the lower index
    const insertIndex = Math.min(currentIndex, targetIndex);
    newSegments.splice(insertIndex, 0, mergedSegment);

    // Update the data
    const newData = {
      ...data,
      segments: newSegments,
      total_segments: newSegments.length
    };
    setData(newData);

    // Update originalTexts array
    const newOriginalTexts = [...originalTexts];
    const originalTextsToRemove = [currentIndex, targetIndex].sort((a, b) => b - a);
    originalTextsToRemove.forEach(index => {
      newOriginalTexts.splice(index, 1);
    });
    newOriginalTexts.splice(insertIndex, 0, mergedText);
    setOriginalTexts(newOriginalTexts);
  };

  const mergeUp = (segmentIndex: number) => {
    mergeWithSegment(segmentIndex, segmentIndex - 1);
  };

  const mergeDown = (segmentIndex: number) => {
    mergeWithSegment(segmentIndex, segmentIndex + 1);
  };

  const showToast = (message: string, type: 'success' | 'error' | 'warning') => {
    setToast({ message, type });
    setTimeout(() => {
      setToast(null);
    }, 3000);
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
    <>
      {/* Fixed elements that should always be visible */}
      {toast && (
        <div
          className="fixed top-4 right-4 z-50"
          style={{
            position: 'fixed',
            top: '1rem',
            right: '1rem',
            zIndex: 50,
            animation: 'slideIn 0.3s ease-out'
          }}
        >
          <div
            className="px-6 py-3 rounded-lg shadow-lg text-white flex items-center space-x-2"
            style={{
              background: toast.type === 'success'
                ? 'linear-gradient(145deg, #10b981, #059669)'
                : toast.type === 'error'
                ? 'linear-gradient(145deg, #ef4444, #dc2626)'
                : 'linear-gradient(145deg, #f59e0b, #d97706)',
              backdropFilter: 'blur(10px)',
              border: '1px solid rgba(255, 255, 255, 0.2)',
              boxShadow: '0 8px 32px rgba(0, 0, 0, 0.3)'
            }}
          >
            <span className="text-lg">
              {toast.type === 'success' ? '✅' : toast.type === 'error' ? '❌' : '⚠️'}
            </span>
            <span className="font-medium">{toast.message}</span>
          </div>
        </div>
      )}

      {/* Fixed floating save button */}
      <div
        style={{
          position: 'fixed',
          bottom: '2rem',
          right: '2rem',
          zIndex: 40
        }}
      >
        <button
          onClick={saveData}
          disabled={saving}
          className="px-6 py-3 rounded-xl text-white font-medium transition-all duration-300 btn-glow shadow-lg"
          style={{
            background: saving
              ? 'linear-gradient(145deg, #6b7280, #9ca3af)'
              : 'var(--gradient-success)',
            boxShadow: '0 10px 25px rgba(0, 0, 0, 0.3), 0 4px 10px rgba(0, 0, 0, 0.2)',
            cursor: saving ? 'not-allowed' : 'pointer',
            opacity: saving ? 0.8 : 1,
            backdropFilter: 'blur(10px)',
            border: '1px solid rgba(255, 255, 255, 0.1)'
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
              <span>保存</span>
            </div>
          )}
        </button>
      </div>

      {/* Main scrollable content */}
      <div className="flex-1 p-8" style={{
        height: '100vh',
        overflowY: 'auto',
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
            className="px-8 py-3 rounded-xl text-white font-medium transition-all duration-300 btn-glow"
            style={{
              background: saving
                ? 'linear-gradient(145deg, #6b7280, #9ca3af)'
                : 'var(--gradient-success)',
              boxShadow: saving ? 'var(--shadow-sm)' : 'var(--shadow-md)',
              cursor: saving ? 'not-allowed' : 'pointer',
              opacity: saving ? 0.7 : 1
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
            key={`${segment.start}-${segment.end}`}
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
                <div className="flex items-center space-x-2">
                  {segment.start > segment.end && (
                    <div className="flex items-center text-xs px-2 py-1 rounded-md" style={{
                      backgroundColor: 'rgba(239, 68, 68, 0.15)',
                      border: '1px solid rgba(239, 68, 68, 0.3)',
                      color: '#f87171'
                    }}>
                      <span className="mr-1">⚠️</span>
                      <span>时间戳异常</span>
                    </div>
                  )}
                  <span className="text-xs font-medium px-3 py-1 rounded-full" style={{
                    background: segment.start > segment.end
                      ? 'linear-gradient(145deg, #f87171, #ef4444)'
                      : 'var(--gradient-info)',
                    color: 'white',
                    boxShadow: 'var(--shadow-sm)'
                  }}>
                    ⏱️ {formatTime(segment.start)} - {formatTime(segment.end)}
                  </span>
                </div>
                <span className="text-xs font-medium" style={{
                  color: 'var(--text-accent)',
                  opacity: 0.8
                }}>
                  段落 {index + 1}
                </span>
              </div>
              {segment.start > segment.end && (
                <div className="p-3 rounded-lg text-xs" style={{
                  backgroundColor: 'rgba(239, 68, 68, 0.08)',
                  border: '1px solid rgba(239, 68, 68, 0.2)',
                  color: '#dc2626',
                  borderRadius: '8px'
                }}>
                  <div className="flex items-start">
                    <span className="mr-2">📍</span>
                    <div>
                      <div className="font-medium mb-1">时间戳检测到异常</div>
                      <div>开始时间 ({segment.start}ms) 晚于结束时间 ({segment.end}ms)</div>
                      <div className="mt-1 text-xs opacity-75">这可能是ASR模型识别造成的异常，建议检查或删除此段落</div>
                    </div>
                  </div>
                </div>
              )}
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
                  }}
                  onBlur={(e) => {
                    e.target.style.borderColor = 'var(--input-border)';
                  }}
                />
                <div className="mt-3 flex items-center justify-between">
                  <div className="flex items-center space-x-3">
                    <button
                      onClick={() => resetSegment(index)}
                      className="px-5 py-2 text-white text-sm font-medium rounded-lg transition-all duration-300 btn-glow"
                      style={{
                        background: 'var(--gradient-secondary)',
                        boxShadow: 'var(--shadow-sm)'
                      }}
                    >
                      <div className="flex items-center space-x-2">
                        <span>🔄</span>
                        <span>复位</span>
                      </div>
                    </button>

                    <button
                      onClick={() => mergeUp(index)}
                      disabled={index === 0}
                      className={`px-5 py-2 text-white text-sm font-medium rounded-lg transition-all duration-300 btn-glow ${
                        index === 0 ? 'opacity-50 cursor-not-allowed' : ''
                      }`}
                      style={{
                        background: index === 0
                          ? 'linear-gradient(145deg, #6b7280, #9ca3af)'
                          : 'linear-gradient(145deg, #3b82f6, #2563eb)',
                        boxShadow: 'var(--shadow-sm)'
                      }}
                    >
                      <div className="flex items-center space-x-2">
                        <span>⬆️</span>
                        <span>向上合并</span>
                      </div>
                    </button>

                    <button
                      onClick={() => mergeDown(index)}
                      disabled={index === data.segments.length - 1}
                      className={`px-5 py-2 text-white text-sm font-medium rounded-lg transition-all duration-300 btn-glow ${
                        index === data.segments.length - 1 ? 'opacity-50 cursor-not-allowed' : ''
                      }`}
                      style={{
                        background: index === data.segments.length - 1
                          ? 'linear-gradient(145deg, #6b7280, #9ca3af)'
                          : 'linear-gradient(145deg, #10b981, #059669)',
                        boxShadow: 'var(--shadow-sm)'
                      }}
                    >
                      <div className="flex items-center space-x-2">
                        <span>⬇️</span>
                        <span>向下合并</span>
                      </div>
                    </button>

                    <button
                      onClick={() => deleteSegment(index)}
                      className="px-5 py-2 text-white text-sm font-medium rounded-lg transition-all duration-300 btn-glow"
                      style={{
                        background: 'linear-gradient(145deg, #ef4444, #dc2626)',
                        boxShadow: 'var(--shadow-sm)'
                      }}
                    >
                      <div className="flex items-center space-x-2">
                        <span>🗑️</span>
                        <span>删除</span>
                      </div>
                    </button>
                  </div>

                  <div className="text-xs" style={{ color: 'var(--text-muted)' }}>
                    {segment.translated_text.split('\n').filter(line => line.trim()).length} 行
                  </div>
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Close main content div */}
      </div>

      {/* Add animations */}
      <style jsx>{`
        @keyframes spin {
          0% { transform: rotate(0deg); }
          100% { transform: rotate(360deg); }
        }

        @keyframes slideIn {
          0% {
            transform: translateX(100%);
            opacity: 0;
          }
          100% {
            transform: translateX(0);
            opacity: 1;
          }
        }

        @keyframes slideOut {
          0% {
            transform: translateX(0);
            opacity: 1;
          }
          100% {
            transform: translateX(100%);
            opacity: 0;
          }
        }
      `}</style>
    </>
  );
}