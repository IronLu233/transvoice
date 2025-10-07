#!/usr/bin/env python3
"""
共享GPU工具模块
提供GPU检测和硬件加速功能，用于多个脚本之间共享GPU相关代码
"""

import subprocess
import sys
import shutil
from typing import Dict, Optional, Tuple


def detect_gpu_support() -> Dict[str, any]:
    """
    检测系统可用的GPU硬件加速支持

    Returns:
        Dict[str, any]: 包含GPU检测结果的字典
            - nvidia: bool 是否支持NVIDIA GPU
            - amd: bool 是否支持AMD GPU
            - intel: bool 是否支持Intel GPU
            - gpu_type: str 检测到的GPU类型
            - available: bool 是否有任何GPU支持
            - details: str 检测详情
    """
    result = {
        'nvidia': False,
        'amd': False,
        'intel': False,
        'gpu_type': 'none',
        'available': False,
        'details': 'No GPU acceleration detected'
    }

    try:
        # 检查FFmpeg是否支持硬件加速
        ffmpeg_result = subprocess.run([
            'ffmpeg', '-hide_banner', '-encoders'
        ], capture_output=True, text=True, timeout=10)

        if ffmpeg_result.returncode != 0:
            result['details'] = 'FFmpeg hardware acceleration check failed'
            return result

        # 检查NVIDIA NVENC
        if 'h264_nvenc' in ffmpeg_result.stdout:
            result['nvidia'] = True
            result['gpu_type'] = 'nvidia'
            result['available'] = True
            result['details'] = 'NVIDIA NVENC GPU acceleration detected'
            return result

        # 检查AMD AMF
        if 'h264_amf' in ffmpeg_result.stdout:
            result['amd'] = True
            result['gpu_type'] = 'amd'
            result['available'] = True
            result['details'] = 'AMD AMF GPU acceleration detected'
            return result

        # 检查Intel QSV
        if 'h264_qsv' in ffmpeg_result.stdout:
            result['intel'] = True
            result['gpu_type'] = 'intel'
            result['available'] = True
            result['details'] = 'Intel QSV GPU acceleration detected'
            return result

        # 检查其他编码器
        encoders = ffmpeg_result.stdout
        if any(encoder in encoders for encoder in ['nvenc', 'amf', 'qsv']):
            result['details'] = 'Hardware acceleration detected but not fully supported'
            result['available'] = True
        else:
            result['details'] = 'No GPU acceleration detected in FFmpeg'

    except subprocess.TimeoutExpired:
        result['details'] = 'GPU detection timeout'
    except FileNotFoundError:
        result['details'] = 'FFmpeg not found'
    except Exception as e:
        result['details'] = f'GPU detection error: {str(e)}'

    return result


def get_ffmpeg_gpu_args(gpu_type: str, preset: str = 'medium') -> list:
    """
    获取FFmpeg GPU硬件加速参数

    Args:
        gpu_type: GPU类型 ('nvidia', 'amd', 'intel', 'none')
        preset: 编码预设 ('fast', 'medium', 'slow', etc.)

    Returns:
        list: FFmpeg GPU参数列表
    """
    if gpu_type == 'nvidia':
        return [
            '-c:v', 'h264_nvenc',
            '-preset', preset,
            '-tune', 'll',  # 低延迟
            '-rc', 'vbr',  # 可变比特率
            '-cq', '20',   # 质量参数
            '-b:v', '2M'   # 目标比特率
        ]
    elif gpu_type == 'amd':
        return [
            '-c:v', 'h264_amf',
            '-quality', preset,
            '-rc', 'vbr',
            '-cq', '20',
            '-b:v', '2M'
        ]
    elif gpu_type == 'intel':
        return [
            '-c:v', 'h264_qsv',
            '-preset', preset,
            '-global_quality', '20',
            '-b:v', '2M'
        ]
    else:
        # CPU编码
        return [
            '-c:v', 'libx264',
            '-preset', preset,
            '-crf', '23',
            '-b:v', '2M'
        ]


def get_ffmpeg_video_to_audio_args(input_path: str, output_path: str, gpu_type: str = 'none') -> list:
    """
    获取视频转音频的FFmpeg命令参数，支持GPU加速

    Args:
        input_path: 输入视频文件路径
        output_path: 输出音频文件路径
        gpu_type: GPU类型

    Returns:
        list: FFmpeg命令参数列表
    """
    base_args = [
        'ffmpeg', '-i', input_path,
        '-vn',  # 忽略视频流
        '-acodec', 'pcm_s16le',  # 16位PCM编码
        '-ar', '16000',  # 采样率16kHz
        '-ac', '1',  # 单声道
        '-y'  # 覆盖输出文件
    ]

    # 对于某些GPU类型，可以添加硬件解码加速
    if gpu_type == 'nvidia':
        # 添加硬件解码
        base_args.insert(1, '-hwaccel')
        base_args.insert(2, 'cuda')
    elif gpu_type == 'intel':
        # 添加硬件解码
        base_args.insert(1, '-hwaccel')
        base_args.insert(2, 'qsv')

    base_args.append(output_path)
    return base_args


def validate_gpu_support(gpu_type: str) -> Tuple[bool, str]:
    """
    验证指定的GPU类型是否可用

    Args:
        gpu_type: 要验证的GPU类型

    Returns:
        Tuple[bool, str]: (是否可用, 详细信息)
    """
    gpu_info = detect_gpu_support()

    if gpu_type == 'nvidia':
        available = gpu_info['nvidia']
        details = gpu_info['details'] if available else 'NVIDIA GPU not available'
    elif gpu_type == 'amd':
        available = gpu_info['amd']
        details = gpu_info['details'] if available else 'AMD GPU not available'
    elif gpu_type == 'intel':
        available = gpu_info['intel']
        details = gpu_info['details'] if available else 'Intel GPU not available'
    else:
        available = True  # CPU总是可用
        details = 'Using CPU encoding'

    return available, details


def print_gpu_info():
    """
    打印GPU检测信息
    """
    print("=" * 60)
    print("GPU硬件加速检测")
    print("=" * 60)

    gpu_info = detect_gpu_support()

    print(f"✓ NVIDIA GPU: {'是' if gpu_info['nvidia'] else '否'}")
    print(f"✓ AMD GPU: {'是' if gpu_info['amd'] else '否'}")
    print(f"✓ Intel GPU: {'是' if gpu_info['intel'] else '否'}")
    print(f"✓ GPU类型: {gpu_info['gpu_type']}")
    print(f"✓ 硬件加速: {'可用' if gpu_info['available'] else '不可用'}")
    print(f"✓ 检测详情: {gpu_info['details']}")
    print("=" * 60)


def main():
    """
    命令行接口：测试GPU检测功能
    """
    if len(sys.argv) > 1 and sys.argv[1] == '--test':
        print_gpu_info()
        return

    # 默认行为：输出JSON格式的检测结果
    import json
    gpu_info = detect_gpu_support()
    print(json.dumps(gpu_info, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()