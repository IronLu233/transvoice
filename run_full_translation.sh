#!/bin/bash

# 视频翻译完整流程自动化脚本
# 用法: ./run_full_translation.sh <input_video_file>
# 示例: ./run_full_translation.sh "video.mp4"

set -e  # 遇到错误立即退出

# 检查参数
if [ $# -eq 0 ]; then
    echo "错误: 请提供输入视频文件路径"
    echo "用法: $0 <input_video_file>"
    echo "示例: $0 \"video.mp4\""
    exit 1
fi

INPUT_FILE="$1"
REFERENCE_AUDIO="/home/iron/transvoice2/data/ICT-ref.WAV"

# 检查输入文件是否存在
if [ ! -f "$INPUT_FILE" ]; then
    echo "错误: 输入文件不存在: $INPUT_FILE"
    exit 1
fi

# 检查参考音频文件是否存在
if [ ! -f "$REFERENCE_AUDIO" ]; then
    echo "错误: 参考音频文件不存在: $REFERENCE_AUDIO"
    exit 1
fi

echo "========================================"
echo "视频翻译完整流程开始"
echo "输入文件: $INPUT_FILE"
echo "参考音频: $REFERENCE_AUDIO"
echo "开始时间: $(date)"
echo "========================================"

# 步骤1: 降噪处理
echo ""
echo "========================================"
echo "步骤1: 降噪处理 (noise_reduction.py)"
echo "========================================"
python noise_reduction.py "$INPUT_FILE"
if [ $? -ne 0 ]; then
    echo "错误: 降噪处理失败"
    exit 1
fi

# 获取降噪后的音频文件路径
DATA_DIR="data/$(basename "$INPUT_FILE" | sed 's/\.[^.]*$//')"
DENOISED_AUDIO="$DATA_DIR/denoised.wav"

if [ ! -f "$DENOISED_AUDIO" ]; then
    echo "错误: 降噪后的音频文件不存在: $DENOISED_AUDIO"
    exit 1
fi

echo "✅ 步骤1完成: 降噪处理成功"
echo "输出文件: $DENOISED_AUDIO"

# 步骤2: ASR语音识别
echo ""
echo "========================================"
echo "步骤2: ASR语音识别 (asr.py)"
echo "========================================"
python asr.py "$DENOISED_AUDIO" --skip-segments
if [ $? -ne 0 ]; then
    echo "错误: ASR语音识别失败"
    exit 1
fi

ASR_RESULTS="$DATA_DIR/denoised_asr_results.json"
if [ ! -f "$ASR_RESULTS" ]; then
    echo "错误: ASR结果文件不存在: $ASR_RESULTS"
    exit 1
fi

echo "✅ 步骤2完成: ASR语音识别成功"
echo "输出文件: $ASR_RESULTS"

# 步骤3: 翻译处理
echo ""
echo "========================================"
echo "步骤3: 翻译处理 (translator.py)"
echo "========================================"
python translator.py "$ASR_RESULTS"
if [ $? -ne 0 ]; then
    echo "错误: 翻译处理失败"
    exit 1
fi

TRANSLATED_RESULTS="$DATA_DIR/denoised_translated_results.json"
if [ ! -f "$TRANSLATED_RESULTS" ]; then
    echo "错误: 翻译结果文件不存在: $TRANSLATED_RESULTS"
    exit 1
fi

echo "✅ 步骤3完成: 翻译处理成功"
echo "输出文件: $TRANSLATED_RESULTS"

# 步骤4: TTS语音合成
echo ""
echo "========================================"
echo "步骤4: TTS语音合成 (tts.py)"
echo "========================================"
python tts.py "$TRANSLATED_RESULTS" "$REFERENCE_AUDIO"
if [ $? -ne 0 ]; then
    echo "错误: TTS语音合成失败"
    exit 1
fi

TTS_OUTPUT_DIR="$DATA_DIR/tts_output"
if [ ! -d "$TTS_OUTPUT_DIR" ]; then
    echo "错误: TTS输出目录不存在: $TTS_OUTPUT_DIR"
    exit 1
fi

TTS_FILE_COUNT=$(ls -1 "$TTS_OUTPUT_DIR"/*.wav 2>/dev/null | wc -l)
echo "✅ 步骤4完成: TTS语音合成成功"
echo "输出目录: $TTS_OUTPUT_DIR"
echo "生成的音频文件数量: $TTS_FILE_COUNT"

# 步骤5: 视频音频合并
echo ""
echo "========================================"
echo "步骤5: 视频音频合并 (video_processor.py)"
echo "========================================"
python video_processor.py "$INPUT_FILE" "$TTS_OUTPUT_DIR"
if [ $? -ne 0 ]; then
    echo "错误: 视频音频合并失败"
    exit 1
fi

# 查找最终输出文件
FINAL_OUTPUT=$(find "$DATA_DIR" -name "*_final.mp4" -o -name "*_final.webm" | head -1)
if [ -z "$FINAL_OUTPUT" ]; then
    # 如果没找到final文件，查找最新的视频文件
    FINAL_OUTPUT=$(find "$DATA_DIR" -name "*.mp4" -o -name "*.webm" -type f -printf '%T@ %p\n' | sort -n | tail -1 | cut -d' ' -f2-)
fi

echo ""
echo "========================================"
echo "🎉 视频翻译流程全部完成!"
echo "========================================"
echo "输入文件: $INPUT_FILE"
echo "最终输出: $FINAL_OUTPUT"
echo "完成时间: $(date)"
echo "总耗时: $SECONDS 秒"
echo ""
echo "输出文件位置:"
echo "- 原始视频: $DATA_DIR/$(basename "$INPUT_FILE")"
echo "- 降噪音频: $DENOISED_AUDIO"
echo "- ASR结果: $ASR_RESULTS"
echo "- 翻译结果: $TRANSLATED_RESULTS"
echo "- TTS音频: $TTS_OUTPUT_DIR/"
echo "- 最终视频: $FINAL_OUTPUT"
echo ""
echo "✅ 所有步骤处理完成!"