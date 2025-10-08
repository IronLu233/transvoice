#!/bin/bash

# TTS和视频合成脚本
# 用法: ./run_tts_and_video.sh <video_path>
# 示例: ./run_tts_and_video.sh "data/02 - ICT Forex - Considerations In Risk Management/02 - ICT Forex - Considerations In Risk Management.mp4"
#
# 注意:
# 1. 视频路径必须是完整的路径（以data开头）
# 2. 翻译文件约定为 denoised_translated_results.json，与视频在同一目录下

set -e  # 遇到错误立即退出

# 检查参数
if [ $# -eq 0 ]; then
    echo "错误: 请提供视频路径"
    echo "用法: $0 <video_path>"
    echo "示例: $0 \"data/02 - ICT Forex - Considerations In Risk Management/02 - ICT Forex - Considerations In Risk Management.mp4\""
    exit 1
fi

VIDEO_PATH="$1"

# 检查路径是否以data开头
if [[ ! "$VIDEO_PATH" =~ ^data/ ]]; then
    echo "错误: 视频路径必须以 'data/' 开头"
    echo "示例: $0 \"data/02 - ICT Forex - Considerations In Risk Management/02 - ICT Forex - Considerations In Risk Management.mp4\""
    exit 1
fi

# 检查视频文件是否存在
if [ ! -f "$VIDEO_PATH" ]; then
    echo "错误: 视频文件不存在: $VIDEO_PATH"
    exit 1
fi

# 获取视频所在目录
VIDEO_DIR=$(dirname "$VIDEO_PATH")
VIDEO_FILENAME=$(basename "$VIDEO_PATH")
VIDEO_BASENAME=$(basename "$VIDEO_FILENAME" | sed 's/\.[^.]*$//')

# 翻译文件路径
TRANSLATED_RESULTS="$VIDEO_DIR/denoised_translated_results.json"

# 检查翻译文件是否存在
if [ ! -f "$TRANSLATED_RESULTS" ]; then
    echo "错误: 翻译文件不存在: $TRANSLATED_RESULTS"
    echo "请确保翻译文件 denoised_translated_results.json 存在于视频同一目录下"
    exit 1
fi

echo "========================================"
echo "TTS和视频合成流程开始"
echo "视频文件: $VIDEO_PATH"
echo "翻译文件: $TRANSLATED_RESULTS"
echo "开始时间: $(date)"
echo "========================================"

# 步骤1: TTS语音合成
echo ""
echo "========================================"
echo "步骤1: TTS语音合成 (tts.py)"
echo "========================================"
python tts.py "$TRANSLATED_RESULTS"
if [ $? -ne 0 ]; then
    echo "错误: TTS语音合成失败"
    exit 1
fi

TTS_OUTPUT_DIR="$VIDEO_DIR/tts_output"
if [ ! -d "$TTS_OUTPUT_DIR" ]; then
    echo "错误: TTS输出目录不存在: $TTS_OUTPUT_DIR"
    exit 1
fi

TTS_FILE_COUNT=$(ls -1 "$TTS_OUTPUT_DIR"/*.wav 2>/dev/null | wc -l)
echo "✅ 步骤1完成: TTS语音合成成功"
echo "输出目录: $TTS_OUTPUT_DIR"
echo "生成的音频文件数量: $TTS_FILE_COUNT"

# 步骤2: 视频音频合成
echo ""
echo "========================================"
echo "步骤2: 视频音频合成 (video_synthesizer.py)"
echo "========================================"
python video_synthesizer.py "$VIDEO_PATH" --tts-dir "$TTS_OUTPUT_DIR"
if [ $? -ne 0 ]; then
    echo "错误: 视频音频合成失败"
    exit 1
fi

# 查找最终输出文件
# video_synthesizer.py 输出文件格式为: 原文件名_synthesized.mp4
FINAL_OUTPUT="$VIDEO_DIR/${VIDEO_BASENAME}_synthesized.mp4"
if [ ! -f "$FINAL_OUTPUT" ]; then
    # 如果没找到synthesized文件，查找最新的视频文件
    FINAL_OUTPUT=$(find "$VIDEO_DIR" -name "*.mp4" -o -name "*.webm" -type f -printf '%T@ %p\n' | sort -n | tail -1 | cut -d' ' -f2-)
fi

echo ""
echo "========================================"
echo "🎉 TTS和视频合成完成!"
echo "========================================"
echo "视频文件: $VIDEO_PATH"
echo "翻译文件: $TRANSLATED_RESULTS"
echo "最终输出: $FINAL_OUTPUT"
echo "完成时间: $(date)"
echo "总耗时: $SECONDS 秒"
echo ""
echo "输出文件位置:"
echo "- 原始视频: $VIDEO_PATH"
echo "- 翻译结果: $TRANSLATED_RESULTS"
echo "- TTS音频: $TTS_OUTPUT_DIR/"
echo "- 最终视频: $FINAL_OUTPUT"
echo ""
echo "✅ 所有步骤处理完成!"