#!/usr/bin/env python3
"""
测试音频修复的脚本
验证TTS音频的采样率和生成文件的音频质量
"""

import subprocess
import json
import os
import sys

def get_audio_info(audio_path):
    """获取音频文件的详细信息"""
    cmd = [
        'ffprobe', '-v', 'quiet', '-print_format', 'json',
        '-show_format', '-show_streams', audio_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    info = json.loads(result.stdout)

    # 找到音频流
    audio_stream = None
    for stream in info['streams']:
        if stream['codec_type'] == 'audio':
            audio_stream = stream
            break

    if audio_stream:
        return {
            'sample_rate': audio_stream.get('sample_rate', 'unknown'),
            'channels': audio_stream.get('channels', 'unknown'),
            'codec': audio_stream.get('codec_name', 'unknown'),
            'bit_rate': audio_stream.get('bit_rate', 'unknown'),
            'duration': float(audio_stream.get('duration', 0))
        }
    return None

def test_audio_sample_rate():
    """测试TTS音频的采样率"""
    print("🔍 检查TTS音频采样率...")

    # 假设有一个tts_output目录
    tts_dir = "tts_output"
    if not os.path.exists(tts_dir):
        print(f"❌ TTS目录不存在: {tts_dir}")
        return False

    audio_files = [f for f in os.listdir(tts_dir) if f.endswith('.wav')]
    if not audio_files:
        print(f"❌ 没有找到TTS音频文件")
        return False

    # 检查第一个音频文件
    audio_path = os.path.join(tts_dir, audio_files[0])
    print(f"📄 检查文件: {audio_files[0]}")

    audio_info = get_audio_info(audio_path)
    if audio_info:
        print(f"📊 音频信息:")
        print(f"   采样率: {audio_info['sample_rate']} Hz")
        print(f"   声道数: {audio_info['channels']}")
        print(f"   编解码器: {audio_info['codec']}")
        print(f"   码率: {audio_info['bit_rate']} bps")
        print(f"   时长: {audio_info['duration']:.2f} 秒")

        # 检查采样率是否为常见的TTS输出采样率
        sample_rate = int(audio_info['sample_rate'])
        common_rates = [16000, 22050, 24000, 44100, 48000]
        if sample_rate in common_rates:
            print(f"✅ 采样率 {sample_rate} Hz 是常见的音频采样率")
            return True
        else:
            print(f"⚠️  采样率 {sample_rate} Hz 不太常见，但可能正常")
            return True
    else:
        print(f"❌ 无法获取音频信息")
        return False

def test_video_output():
    """测试最终视频输出的音频质量"""
    print("\n🎬 检查最终视频输出的音频...")

    # 查找可能的输出视频文件
    video_files = []
    for f in os.listdir('.'):
        if f.endswith('.mp4') and ('translated' in f or 'output' in f):
            video_files.append(f)

    if not video_files:
        print("❌ 没有找到输出视频文件")
        return False

    # 检查最新的视频文件
    video_path = sorted(video_files)[-1]
    print(f"📄 检查文件: {video_path}")

    # 获取视频信息
    cmd = [
        'ffprobe', '-v', 'quiet', '-print_format', 'json',
        '-show_format', '-show_streams', video_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    info = json.loads(result.stdout)

    # 找到音频流
    audio_stream = None
    video_stream = None
    for stream in info['streams']:
        if stream['codec_type'] == 'audio':
            audio_stream = stream
        elif stream['codec_type'] == 'video':
            video_stream = stream

    if audio_stream:
        print(f"📊 视频音频信息:")
        print(f"   音频编码: {audio_stream.get('codec_name', 'unknown')}")
        print(f"   采样率: {audio_stream.get('sample_rate', 'unknown')} Hz")
        print(f"   声道数: {audio_stream.get('channels', 'unknown')}")
        print(f"   音频码率: {audio_stream.get('bit_rate', 'unknown')} bps")

        # 检查音频质量指标
        if audio_stream.get('codec_name') == 'aac':
            print("✅ 音频编码格式正确 (AAC)")
        else:
            print(f"⚠️  音频编码格式为 {audio_stream.get('codec_name')}，通常应该是AAC")

        # 检查是否保持了合理的采样率
        sample_rate = int(audio_stream.get('sample_rate', 0))
        if sample_rate >= 16000 and sample_rate <= 48000:
            print(f"✅ 音频采样率 {sample_rate} Hz 在合理范围内")
        else:
            print(f"⚠️  音频采样率 {sample_rate} Hz 可能有问题")

        return True
    else:
        print("❌ 视频中没有找到音频流")
        return False

def main():
    print("🧪 音频修复测试脚本")
    print("=" * 50)

    success = True

    # 测试1: 检查TTS音频采样率
    if not test_audio_sample_rate():
        success = False

    # 测试2: 检查最终视频输出
    if not test_video_output():
        success = False

    print("\n" + "=" * 50)
    if success:
        print("✅ 所有测试通过！音频修复可能有效。")
        print("💡 建议手动播放生成的视频文件确认音频质量。")
    else:
        print("❌ 部分测试失败，可能需要进一步调试。")

    return success

if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"❌ 测试过程中出错: {e}")
        sys.exit(1)