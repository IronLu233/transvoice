#!/usr/bin/env python3
"""
视频翻译最后一步：将TTS生成的音频与视频合成
支持视频速度调整以匹配新的音频长度
支持GPU加速编码
"""

import os
import re
import json
import subprocess
import tempfile
import argparse
import time
import sys
from pathlib import Path
from typing import List, Tuple, Optional, Dict
from gpu_utils import detect_gpu_support, get_ffmpeg_gpu_args, validate_gpu_support, print_gpu_info


class VideoProcessor:
    def __init__(self, gpu_acceleration: bool = False, gpu_type: str = 'auto', preset: str = 'fast'):
        self.temp_dir = None
        self.gpu_acceleration = gpu_acceleration
        self.gpu_type = gpu_type
        self.preset = preset
        self.start_time = time.time()
        self.gpu_info = self._initialize_gpu_support()

        if gpu_acceleration:
            print(f"GPU加速已启用: {self.gpu_info['encoder']} ({self.gpu_info['description']})")

    def log(self, message: str, level: str = "INFO"):
        """输出带时间戳的日志"""
        timestamp = time.strftime("%H:%M:%S", time.localtime())
        print(f"[{timestamp}] {level}: {message}")
        sys.stdout.flush()  # 确保立即输出

    def show_progress(self, current: int, total: int, task: str = "处理"):
        """显示进度条"""
        percent = (current / total) * 100
        filled = int(50 * current // total)
        bar = '█' * filled + '-' * (50 - filled)
        print(f'\r{task}进度: |{bar}| {percent:.1f}% ({current}/{total})', end='', flush=True)

        if current == total:
            print()  # 完成时换行

    def get_elapsed_time(self) -> str:
        """获取已用时间"""
        elapsed = time.time() - self.start_time
        minutes, seconds = divmod(int(elapsed), 60)
        return f"{minutes:02d}:{seconds:02d}"

    def _initialize_gpu_support(self) -> Dict:
        """初始化GPU支持"""
        if not self.gpu_acceleration:
            return {
                'available': False,
                'type': 'cpu',
                'encoder': 'libx264',
                'description': 'CPU编码'
            }

        # 使用共享GPU工具模块检测
        gpu_info = detect_gpu_support()

        # 转换为兼容格式
        if gpu_info['available']:
            return {
                'available': True,
                'type': gpu_info['gpu_type'],
                'encoder': f"h264_{gpu_info['gpu_type']}",
                'description': gpu_info['details']
            }
        else:
            return {
                'available': False,
                'type': 'cpu',
                'encoder': 'libx264',
                'description': 'CPU编码'
            }

    def get_gpu_preset(self) -> str:
        """根据GPU类型和预设获取编码参数"""
        if not self.gpu_acceleration or not self.gpu_info['available']:
            return self.preset

        # 直接使用预设值，因为共享模块已经处理了预设映射
        return self.preset

    def build_ffmpeg_command(self, base_cmd: List[str], use_gpu: bool = True) -> List[str]:
        """构建支持GPU的FFmpeg命令"""
        if not use_gpu or not self.gpu_acceleration or not self.gpu_info['available']:
            return base_cmd

        # 使用共享GPU工具模块构建命令
        if self.gpu_info['type'] == 'nvidia':
            # 检查是否已经有输入文件
            if '-i' in base_cmd:
                input_index = base_cmd.index('-i')
                if input_index + 1 < len(base_cmd):
                    # 在输入文件前添加硬件加速参数
                    insert_index = input_index
                    hwaccel_cmd = ['-hwaccel', 'cuda', '-hwaccel_output_format', 'cuda']
                    base_cmd[insert_index:insert_index] = hwaccel_cmd

        return base_cmd

    def __enter__(self):
        # 使用固定的tmp目录作为临时文件夹
        import os
        self.temp_dir = "tmp"
        if os.path.exists(self.temp_dir):
            # 清空已存在的tmp目录
            import shutil
            shutil.rmtree(self.temp_dir)
        os.makedirs(self.temp_dir)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # 保留临时文件用于调试，不再自动清理
        if self.temp_dir and os.path.exists(self.temp_dir):
            self.log(f"📁 临时文件保留在: {self.temp_dir}")
            self.log("💡 提示: 临时文件不会自动删除，如需清理请手动删除该目录")

        # 注释掉自动清理代码
        # if self.temp_dir and os.path.exists(self.temp_dir):
        #     import shutil
        #     shutil.rmtree(self.temp_dir)

    def get_video_info(self, video_path: str) -> dict:
        """获取视频信息"""
        self.log(f"获取视频信息: {os.path.basename(video_path)}")
        cmd = [
            'ffprobe', '-v', 'quiet', '-print_format', 'json',
            '-show_format', '-show_streams', video_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        info = json.loads(result.stdout)
        duration = float(info['format']['duration'])
        self.log(f"视频时长: {duration:.2f}秒 ({duration/60:.2f}分钟)")
        return info

    def get_audio_duration(self, audio_path: str) -> float:
        """获取音频文件时长（秒）"""
        cmd = [
            'ffprobe', '-v', 'quiet', '-show_entries',
            'format=duration', '-of', 'csv=p=0', audio_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        duration = float(result.stdout.strip())
        return duration

    def get_video_duration(self, video_path: str) -> float:
        """获取视频文件时长（秒）"""
        cmd = [
            'ffprobe', '-v', 'quiet', '-show_entries',
            'format=duration', '-of', 'csv=p=0', video_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        duration = float(result.stdout.strip())
        return duration

    def parse_audio_filename(self, filename: str) -> Optional[Tuple[int, int]]:
        """
        解析音频文件名，提取开始和结束时间

        Args:
            filename: 音频文件名，格式为 tts_{start}_{end}_{hash}.wav

        Returns:
            Tuple[int, int]: (开始时间毫秒, 结束时间毫秒) 或 None
        """
        pattern = r'tts_(\d+)_(\d+)_[\w\d]+\.wav'
        match = re.match(pattern, filename)
        if match:
            start_ms = int(match.group(1))
            end_ms = int(match.group(2))
            return start_ms, end_ms
        return None

    def create_speed_adjusted_video_segment(self, input_video: str, start_time: float,
                                          end_time: float, target_duration: float,
                                          output_path: str) -> bool:
        """
        创建调整了速度的视频片段

        Args:
            input_video: 输入视频路径
            start_time: 开始时间（秒）
            end_time: 结束时间（秒）
            target_duration: 目标时长（秒）
            output_path: 输出路径

        Returns:
            bool: 是否成功
        """
        original_duration = end_time - start_time

        if abs(original_duration - target_duration) < 0.01:  # 差异小于10ms，不需要调整
            speed_factor = 1.0
            self.log(f"提取视频片段: {start_time:.2f}-{end_time:.2f}s (无需调速)")
        else:
            speed_factor = original_duration / target_duration
            self.log(f"调整视频速度: {start_time:.2f}-{end_time:.2f}s, 速度因子: {speed_factor:.2f}x")

        try:
            # 检查片段时长是否过短
            if original_duration < 0.1:  # 少于100ms的片段
                self.log(f"  ⚠️  片段过短 ({original_duration:.3f}s)，跳过")
                # 创建一个空的但有效的文件
                cmd = [
                    'ffmpeg', '-y', '-f', 'lavfi', '-i', 'color=c=black:s=1920x1080:d=0.1:rate=30',
                    '-t', '0.1',
                    '-c:v', 'libx264',
                    '-preset', 'ultrafast',
                    '-crf', '23',
                    '-pix_fmt', 'yuv420p',
                    output_path
                ]
                subprocess.run(cmd, check=True, capture_output=True)
                self.log(f"  ✅ 创建了占位片段")
                return True

            if abs(speed_factor - 1.0) < 0.01:  # 基本不需要调整速度
                # 直接提取视频片段
                self.log(f"  提取片段: 原时长 {original_duration:.2f}s")
                cmd = [
                    'ffmpeg', '-y', '-i', input_video,
                    '-ss', str(start_time),
                    '-t', str(original_duration),
                    '-c:v', 'copy',
                    '-avoid_negative_ts', '1',
                    output_path
                ]
                cmd = self.build_ffmpeg_command(cmd, use_gpu=False)  # 复制模式不需要GPU
                try:
                    result = subprocess.run(cmd, check=True, capture_output=True)
                    # 检查输出文件是否有效
                    if os.path.exists(output_path) and os.path.getsize(output_path) > 1024:
                        self.log(f"  ✅ 片段提取完成")
                    else:
                        raise subprocess.CalledProcessError(1, cmd, "输出文件无效")
                except subprocess.CalledProcessError:
                    # 复制模式失败，使用重新编码
                    self.log(f"  🔧 复制模式失败，使用重新编码...")
                    cmd_reencode = [
                        'ffmpeg', '-y', '-i', input_video,
                        '-ss', str(start_time),
                        '-t', str(max(original_duration, 0.1)),  # 确保最少0.1秒
                        '-c:v', 'libx264',
                        '-preset', 'ultrafast',  # 使用超快预设
                        '-crf', '23',
                        '-avoid_negative_ts', '1',
                        '-pix_fmt', 'yuv420p',
                        output_path
                    ]
                    result = subprocess.run(cmd_reencode, check=True, capture_output=True)
                    # 检查输出文件
                    if os.path.exists(output_path) and os.path.getsize(output_path) > 1024:
                        self.log(f"  ✅ 重新编码提取完成")
                    else:
                        raise subprocess.CalledProcessError(1, cmd_reencode, "重新编码后文件仍然无效")
            else:
                # 需要调整速度
                # 首先提取视频片段
                temp_segment = os.path.join(self.temp_dir, f"temp_segment_{os.getpid()}_{int(start_time*1000)}.mp4")
                self.log(f"  步骤1: 提取原始片段...")
                cmd = [
                    'ffmpeg', '-y', '-i', input_video,
                    '-ss', str(start_time),
                    '-t', str(original_duration),
                    '-c:v', 'copy',
                    '-avoid_negative_ts', '1',
                    temp_segment
                ]
                cmd = self.build_ffmpeg_command(cmd, use_gpu=True)  # 可以使用GPU加速解码
                subprocess.run(cmd, check=True, capture_output=True)

                # 只调整视频速度，不处理音频（因为处理的是静音视频）
                video_filter = f"[0:v]setpts={1/speed_factor}*PTS[v]"
                encoder_type = "GPU" if (self.gpu_acceleration and self.gpu_info['available']) else "CPU"
                self.log(f"  步骤2: 调整速度 ({encoder_type}编码)...")

                # 构建编码命令 - 使用共享GPU工具模块
                if self.gpu_acceleration and self.gpu_info['available']:
                    # 使用共享GPU工具获取编码参数
                    gpu_args = get_ffmpeg_gpu_args(self.gpu_info['type'], self.get_gpu_preset())
                    cmd = [
                        'ffmpeg', '-y', '-i', temp_segment,
                        '-filter_complex', video_filter,
                        '-map', '[v]',
                        *gpu_args,
                        '-pix_fmt', 'yuv420p',
                        output_path
                    ]
                else:
                    # CPU编码
                    cmd = [
                        'ffmpeg', '-y', '-i', temp_segment,
                        '-filter_complex', video_filter,
                        '-map', '[v]',
                        '-c:v', 'libx264', '-preset', self.preset,
                        '-crf', '23',
                        '-pix_fmt', 'yuv420p',
                        output_path
                    ]

                subprocess.run(cmd, check=True, capture_output=True)
                self.log(f"  ✅ 速度调整完成: {original_duration:.2f}s → {target_duration:.2f}s")

                # 清理临时文件
                if os.path.exists(temp_segment):
                    os.remove(temp_segment)

            return True

        except subprocess.CalledProcessError as e:
            self.log(f"❌ 创建速度调整视频片段失败: {e}", "ERROR")
            return False

    def merge_audio_with_video(self, video_path: str, audio_path: str, output_path: str) -> bool:
        """
        两步法：1)提取纯视频 2)合并TTS音频，确保只有一个音频流

        Args:
            video_path: 视频路径（包含原音频流）
            audio_path: TTS音频路径
            output_path: 输出路径

        Returns:
            bool: 是否成功
        """
        try:
            # 验证输入文件存在
            if not os.path.exists(video_path):
                self.log(f"  ❌ 视频文件不存在: {video_path}", "ERROR")
                return False
            if not os.path.exists(audio_path):
                self.log(f"  ❌ TTS音频文件不存在: {audio_path}", "ERROR")
                return False

            # 获取视频和TTS音频的时长
            video_duration = self.get_video_duration(video_path)
            audio_duration = self.get_audio_duration(audio_path)

            self.log(f"  视频时长: {video_duration:.2f}s, TTS音频时长: {audio_duration:.2f}s")

            # 步骤1: 提取纯视频（无音频）
            self.log(f"  步骤1: 提取纯视频...")
            temp_video_only = os.path.join(self.temp_dir, f"pure_video_{os.getpid()}.mp4")
            extract_cmd = [
                'ffmpeg', '-y',
                '-i', video_path,
                '-c:v', 'copy',           # 复制视频流
                '-an',                    # 去掉音频流
                temp_video_only
            ]

            try:
                subprocess.run(extract_cmd, check=True, capture_output=True)
                self.log(f"  ✅ 纯视频提取完成")
            except subprocess.CalledProcessError as e:
                self.log(f"  ❌ 提取纯视频失败: {e}", "ERROR")
                return False

            # 步骤2: 将TTS音频处理到与视频等长
            self.log(f"  步骤2: 处理TTS音频...")
            processed_audio = None

            if audio_duration > video_duration:
                # TTS音频比视频长，截断TTS音频
                self.log(f"  🔪 TTS音频比视频长 {(audio_duration - video_duration):.2f}s，截断TTS音频")
                processed_audio = os.path.join(self.temp_dir, f"processed_audio_{os.getpid()}.aac")
                cut_cmd = [
                    'ffmpeg', '-y',
                    '-i', audio_path,
                    '-c:a', 'aac',
                    '-ac', '1',
                    '-b:a', '128k',
                    '-t', str(video_duration),
                    processed_audio
                ]
                subprocess.run(cut_cmd, check=True, capture_output=True)

            elif audio_duration < video_duration - 0.1:  # 允许0.1秒误差
                # TTS音频比视频短很多，填充静音
                self.log(f"  🔇 TTS音频比视频短 {(video_duration - audio_duration):.2f}s，填充静音")
                processed_audio = os.path.join(self.temp_dir, f"processed_audio_{os.getpid()}.aac")
                pad_cmd = [
                    'ffmpeg', '-y',
                    '-i', audio_path,
                    '-c:a', 'aac',
                    '-ac', '1',
                    '-b:a', '128k',
                    '-filter_complex', 'apad=pad_dur=' + str(video_duration - audio_duration),
                    '-t', str(video_duration),
                    processed_audio
                ]
                subprocess.run(pad_cmd, check=True, capture_output=True)
            else:
                # TTS音频和视频时长基本匹配，直接使用原TTS音频
                self.log(f"  ✅ TTS音频和视频时长匹配，直接使用")
                processed_audio = audio_path

            # 步骤3: 合并纯视频和处理后的TTS音频
            self.log(f"  步骤3: 合并纯视频与TTS音频...")
            merge_cmd = [
                'ffmpeg', '-y',
                '-i', temp_video_only,
                '-i', processed_audio,
                '-c:v', 'copy',           # 复制视频流
                '-c:a', 'copy',           # 复制已处理的音频流
                '-map', '0:v:0',          # 纯视频流
                '-map', '1:a:0',          # TTS音频流
                '-t', str(video_duration), # 确保时长匹配
                output_path
            ]

            try:
                subprocess.run(merge_cmd, check=True, capture_output=True)
                self.log(f"  ✅ 合并完成")
            except subprocess.CalledProcessError as e:
                self.log(f"  ❌ 合并失败: {e}", "ERROR")
                return False

            # 保留临时文件用于调试，不自动清理
            self.log(f"  📁 临时文件保留:")
            self.log(f"    - 纯视频: {temp_video_only}")
            if processed_audio != audio_path:
                self.log(f"    - 处理后的音频: {processed_audio}")

            # 验证输出文件是否存在且有效
            if not os.path.exists(output_path):
                self.log(f"  ❌ 输出文件未创建: {output_path}", "ERROR")
                return False

            output_size = os.path.getsize(output_path)
            if output_size < 1024:
                self.log(f"  ❌ 输出文件过小: {output_size} bytes", "ERROR")
                return False

            # 验证输出文件的流信息
            try:
                # 检查流的数量
                streams = subprocess.run([
                    'ffprobe', '-v', 'quiet', '-show_entries',
                    'stream=codec_type', '-of', 'csv=p=0', output_path
                ], capture_output=True, text=True, check=True).stdout.strip().split('\n')

                video_streams = [s for s in streams if s == 'video']
                audio_streams = [s for s in streams if s == 'audio']

                self.log(f"  📊 输出流信息: 视频{len(video_streams)}个, 音频{len(audio_streams)}个")

                if len(video_streams) != 1 or len(audio_streams) != 1:
                    self.log(f"  ❌ 流数量异常: 预期1个视频流+1个音频流，实际{len(video_streams)}个视频+{len(audio_streams)}个音频", "ERROR")
                    return False

                # 检查视频和音频流的时长
                video_dur = float(subprocess.run([
                    'ffprobe', '-v', 'quiet', '-show_entries',
                    'stream=duration', '-select_streams', 'v',
                    '-of', 'csv=p=0', output_path
                ], capture_output=True, text=True, check=True).stdout.strip())

                audio_dur = float(subprocess.run([
                    'ffprobe', '-v', 'quiet', '-show_entries',
                    'stream=duration', '-select_streams', 'a',
                    '-of', 'csv=p=0', output_path
                ], capture_output=True, text=True, check=True).stdout.strip())

                # 验证视频和音频时长是否匹配
                duration_diff = abs(video_dur - audio_dur)
                if duration_diff > 0.1:  # 允许0.1秒误差
                    self.log(f"  ⚠️  音频和视频时长不匹配: 视频{video_dur:.2f}s, 音频{audio_dur:.2f}s, 差异{duration_diff:.2f}s", "WARNING")
                else:
                    self.log(f"  ✅ 音频和视频时长完美匹配: 视频{video_dur:.2f}s, 音频{audio_dur:.2f}s")

            except Exception as e:
                self.log(f"  ⚠️  无法验证音视频时长匹配: {e}", "WARNING")

            self.log(f"  ✅ TTS音频替换完成: 输出时长{self.get_video_duration(output_path):.2f}s")

            return True
        except subprocess.CalledProcessError as e:
            self.log(f"❌ 合并TTS音频失败: {e}", "ERROR")
            return False

    def create_silent_video(self, input_video: str, output_path: str) -> bool:
        """
        创建静音版本的视频

        Args:
            input_video: 输入视频路径
            output_path: 输出路径

        Returns:
            bool: 是否成功
        """
        try:
            cmd = [
                'ffmpeg', '-y', '-i', input_video,
                '-c:v', 'copy', '-an',
                output_path
            ]
            subprocess.run(cmd, check=True, capture_output=True)
            return True
        except subprocess.CalledProcessError as e:
            print(f"创建静音视频失败: {e}")
            return False

    def create_silent_audio_video(self, input_video: str, output_path: str, duration: float) -> bool:
        """
        创建带静音音频的视频

        Args:
            input_video: 输入视频路径
            output_path: 输出路径
            duration: 视频时长

        Returns:
            bool: 是否成功
        """
        try:
            # 创建带静音音频的视频，使用与TTS音频相同的采样率
            cmd = [
                'ffmpeg', '-y',
                '-i', input_video,  # 输入视频
                '-f', 'lavfi', '-i', 'anullsrc=channel_layout=mono:sample_rate=22050',  # 静音音频源
                '-c:v', 'copy',  # 复制视频流
                '-c:a', 'aac',   # 编码静音音频为AAC
                '-ar', '22050',  # 统一采样率为22050Hz
                '-ac', '1',      # 单声道
                '-b:a', '128k',  # 音频码率
                '-map', '0:v:0', # 映射视频流
                '-map', '1:a:0', # 映射静音音频流
                '-t', str(duration),  # 确保时长匹配
                '-shortest',     # 以最短流为准
                output_path
            ]
            subprocess.run(cmd, check=True, capture_output=True)
            return True
        except subprocess.CalledProcessError as e:
            self.log(f"创建静音音频视频失败: {e}", "ERROR")
            return False

    def create_video_segment_with_audio(self, input_video: str, start_time: float,
                                       end_time: float, output_path: str) -> bool:
        """
        创建带音频的视频片段（从原视频直接裁剪，保持音轨）

        Args:
            input_video: 输入视频路径
            start_time: 开始时间（秒）
            end_time: 结束时间（秒）
            output_path: 输出路径

        Returns:
            bool: 是否成功
        """
        duration = end_time - start_time

        try:
            # 直接从原视频裁剪，保持音轨
            self.log(f"  裁剪视频片段: {start_time:.2f}-{end_time:.2f}s ({duration:.2f}s)")
            cmd = [
                'ffmpeg', '-y',
                '-i', input_video,
                '-ss', str(start_time),
                '-t', str(duration),
                '-c:v', 'copy',  # 视频流复制
                '-c:a', 'copy',  # 音频流复制
                '-avoid_negative_ts', '1',
                output_path
            ]

            # 构建GPU加速命令（如果可用）
            cmd = self.build_ffmpeg_command(cmd, use_gpu=True)

            subprocess.run(cmd, check=True, capture_output=True)

            # 检查输出文件是否有效
            if os.path.exists(output_path) and os.path.getsize(output_path) > 1024:
                return True
            else:
                # 如果复制失败，尝试重新编码
                self.log(f"  🔧 复制模式失败，尝试重新编码...")
                cmd_reencode = [
                    'ffmpeg', '-y',
                    '-i', input_video,
                    '-ss', str(start_time),
                    '-t', str(max(duration, 0.1)),
                    '-c:v', 'libx264',
                    '-preset', 'ultrafast',
                    '-crf', '23',
                    '-c:a', 'aac',
                    '-avoid_negative_ts', '1',
                    '-pix_fmt', 'yuv420p',
                    output_path
                ]
                subprocess.run(cmd_reencode, check=True, capture_output=True)
                return os.path.exists(output_path) and os.path.getsize(output_path) > 1024

        except subprocess.CalledProcessError as e:
            self.log(f"❌ 创建视频片段失败: {e}", "ERROR")
            return False

    def adjust_video_speed_with_audio(self, input_video: str, speed_factor: float,
                                     output_path: str) -> bool:
        """
        调整带音频视频的速度（同时调整视频和音频）

        Args:
            input_video: 输入视频路径
            speed_factor: 速度因子（>1加速，<1减速）
            output_path: 输出路径

        Returns:
            bool: 是否成功
        """
        try:
            self.log(f"  调整视频速度: {speed_factor:.2f}x")

            # 同时调整视频和音频速度
            video_filter = f"[0:v]setpts={1/speed_factor}*PTS[v]"
            audio_filter = f"[0:a]atempo={speed_factor}[a]"

            # 对于GPU模式，先使用CPU处理滤镜，然后可以后续转换为GPU编码
            # 因为filter_complex与GPU编码器可能不兼容
            if self.gpu_acceleration and self.gpu_info['available']:
                # 使用GPU解码但CPU编码处理滤镜
                cmd = [
                    'ffmpeg', '-y',
                    '-hwaccel', 'cuda', '-hwaccel_output_format', 'cuda',
                    '-i', input_video,
                    '-filter_complex', f'{video_filter};{audio_filter}',
                    '-map', '[v]',
                    '-map', '[a]',
                    '-c:v', 'libx264',  # 使用CPU编码处理滤镜
                    '-preset', self.preset,
                    '-crf', '23',
                    '-c:a', 'aac',
                    '-pix_fmt', 'yuv420p',
                    output_path
                ]
            else:
                # 纯CPU模式
                cmd = [
                    'ffmpeg', '-y',
                    '-i', input_video,
                    '-filter_complex', f'{video_filter};{audio_filter}',
                    '-map', '[v]',
                    '-map', '[a]',
                    '-c:v', 'libx264',
                    '-preset', self.preset,
                    '-crf', '23',
                    '-c:a', 'aac',
                    '-pix_fmt', 'yuv420p',
                    output_path
                ]

            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                # 如果GPU解码失败，尝试纯CPU
                if self.gpu_acceleration and self.gpu_info['available']:
                    self.log(f"  ⚠️  GPU解码失败，尝试纯CPU模式...")
                    cmd_cpu = [
                        'ffmpeg', '-y',
                        '-i', input_video,
                        '-filter_complex', f'{video_filter};{audio_filter}',
                        '-map', '[v]',
                        '-map', '[a]',
                        '-c:v', 'libx264',
                        '-preset', self.preset,
                        '-crf', '23',
                        '-c:a', 'aac',
                        '-pix_fmt', 'yuv420p',
                        output_path
                    ]
                    subprocess.run(cmd_cpu, check=True, capture_output=True)
                else:
                    raise subprocess.CalledProcessError(result.returncode, cmd, result.stderr)

            return True

        except subprocess.CalledProcessError as e:
            self.log(f"❌ 调整视频速度失败: {e}", "ERROR")
            return False

    def process_video_translation(self, video_path: str, audio_dir: str, output_path: str) -> bool:
        """
        处理视频翻译的主要流程 - 新的4步流程

        Args:
            video_path: 原视频路径
            audio_dir: TTS音频文件夹路径
            output_path: 输出视频路径

        Returns:
            bool: 是否成功
        """
        self.log("=" * 60)
        self.log("🚀 开始视频翻译处理（新4步流程）", "INFO")
        self.log(f"输入视频: {os.path.basename(video_path)}")
        self.log(f"音频目录: {audio_dir}")
        self.log(f"输出文件: {os.path.basename(output_path)}")
        self.log(f"GPU加速: {self.gpu_info['description'] if self.gpu_acceleration else 'CPU编码'}")
        self.log(f"编码预设: {self.preset}")
        self.log("=" * 60)

        # 检查输入文件
        if not os.path.exists(video_path):
            self.log(f"❌ 错误: 视频文件不存在: {video_path}", "ERROR")
            return False

        if not os.path.exists(audio_dir):
            self.log(f"❌ 错误: 音频目录不存在: {audio_dir}", "ERROR")
            return False

        # 获取视频时长
        try:
            self.log("📊 分析视频文件...")
            video_info = self.get_video_info(video_path)
            video_duration = float(video_info['format']['duration'])
        except Exception as e:
            self.log(f"❌ 获取视频信息失败: {e}", "ERROR")
            return False

        # 扫描音频文件
        self.log("🔍 扫描音频文件...")
        audio_files = []
        for filename in os.listdir(audio_dir):
            if filename.endswith('.wav'):
                time_info = self.parse_audio_filename(filename)
                if time_info:
                    start_ms, end_ms = time_info
                    audio_path = os.path.join(audio_dir, filename)
                    audio_duration = self.get_audio_duration(audio_path)

                    audio_files.append({
                        'filename': filename,
                        'path': audio_path,
                        'original_start': start_ms / 1000.0,  # 转换为秒
                        'original_end': end_ms / 1000.0,
                        'original_duration': (end_ms - start_ms) / 1000.0,
                        'new_duration': audio_duration
                    })

        if not audio_files:
            self.log("❌ 错误: 没有找到有效的音频文件", "ERROR")
            return False

        # 按开始时间排序
        audio_files.sort(key=lambda x: x['original_start'])

        self.log(f"✅ 找到 {len(audio_files)} 个音频文件")
        total_original_duration = sum(audio['original_duration'] for audio in audio_files)
        total_new_duration = sum(audio['new_duration'] for audio in audio_files)
        self.log(f"📏 原始音频总时长: {total_original_duration:.2f}秒")
        self.log(f"📏 新音频总时长: {total_new_duration:.2f}秒")
        self.log(f"⏱️  时间变化: {total_new_duration/total_original_duration:.2f}x")

        # 步骤1: 对原视频带着音轨进行裁剪，得到若干个带说话声音的视频片段，和没说话时的视频片段
        self.log("\n✂️  步骤1: 裁剪原视频（带音轨）...")
        current_time = 0.0
        original_segments = []  # 存储所有片段信息

        for i, audio in enumerate(audio_files):
            self.log(f"\n📹 处理第 {i+1}/{len(audio_files)} 个音频片段")
            self.show_progress(i+1, len(audio_files), "裁剪视频")

            # 处理间隙（不包含说话的部分）
            if audio['original_start'] > current_time:
                gap_start = current_time
                gap_end = audio['original_start']
                gap_duration = gap_end - gap_start

                self.log(f"  间隙片段: {gap_start:.2f}-{gap_end:.2f}s ({gap_duration:.2f}s)")

                # 过滤没说话时音频太短（<1秒）的片段
                if gap_duration < 1.0:
                    self.log(f"  ⚠️  间隙片段太短 ({gap_duration:.2f}s < 1s)，直接丢弃")
                else:
                    gap_path = os.path.join(self.temp_dir, f"step1_gap_{i}.mp4")
                    if self.create_video_segment_with_audio(video_path, gap_start, gap_end, gap_path):
                        # 为gap片段创建静音音频版本（避免原始音频的兼容性问题）
                        silent_gap_path = os.path.join(self.temp_dir, f"step1_gap_{i}_silent.mp4")
                        if self.create_silent_audio_video(gap_path, silent_gap_path, gap_duration):
                            original_segments.append({
                                'path': silent_gap_path,  # 使用静音版本
                                'start': gap_start,
                                'end': gap_end,
                                'duration': gap_duration,
                                'type': 'gap',  # 间隙片段
                                'speed_factor': 1.0  # 间隙片段不调速
                            })
                            self.log(f"    ✅ 创建静音gap片段")
                        else:
                            # 如果静音化失败，使用原始片段
                            original_segments.append({
                                'path': gap_path,
                                'start': gap_start,
                                'end': gap_end,
                                'duration': gap_duration,
                                'type': 'gap',  # 间隙片段
                                'speed_factor': 1.0  # 间隙片段不调速
                            })
                            self.log(f"    ⚠️  静音化失败，使用原始gap片段")

            # 处理说话部分（带音频）
            speech_path = os.path.join(self.temp_dir, f"step1_speech_{i}.mp4")
            self.log(f"  说话片段: {audio['original_start']:.2f}-{audio['original_end']:.2f}s")

            if self.create_video_segment_with_audio(
                video_path, audio['original_start'], audio['original_end'], speech_path
            ):
                original_segments.append({
                    'path': speech_path,
                    'start': audio['original_start'],
                    'end': audio['original_end'],
                    'duration': audio['original_duration'],
                    'type': 'speech',  # 说话片段
                    'audio_file': audio,  # 关联的音频文件
                    'speed_factor': None  # 将在步骤2中计算
                })

            current_time = audio['original_end']

        # 处理尾部片段
        if current_time < video_duration:
            tail_start = current_time
            tail_duration = video_duration - tail_start
            tail_path = os.path.join(self.temp_dir, "step1_tail.mp4")

            self.log(f"\n🎯 尾部片段: {tail_start:.2f}-{video_duration:.2f}s ({tail_duration:.2f}s)")

            if tail_duration < 1.0:
                self.log(f"  ⚠️  尾部片段太短 ({tail_duration:.2f}s < 1s)，直接丢弃")
            else:
                if self.create_video_segment_with_audio(video_path, tail_start, video_duration, tail_path):
                    # 为尾部片段创建静音音频版本
                    silent_tail_path = os.path.join(self.temp_dir, "step1_tail_silent.mp4")
                    if self.create_silent_audio_video(tail_path, silent_tail_path, tail_duration):
                        original_segments.append({
                            'path': silent_tail_path,  # 使用静音版本
                            'start': tail_start,
                            'end': video_duration,
                            'duration': tail_duration,
                            'type': 'tail',  # 尾部片段
                            'speed_factor': 1.0  # 尾部片段不调速
                        })
                        self.log(f"    ✅ 创建静音尾部片段")
                    else:
                        # 如果静音化失败，使用原始片段
                        original_segments.append({
                            'path': tail_path,
                            'start': tail_start,
                            'end': video_duration,
                            'duration': tail_duration,
                            'type': 'tail',  # 尾部片段
                            'speed_factor': 1.0  # 尾部片段不调速
                        })
                        self.log(f"    ⚠️  静音化失败，使用原始尾部片段")

        self.log(f"\n✅ 步骤1完成: 生成了 {len(original_segments)} 个带音频的视频片段")

        # 完成第一个任务
        self.todo_write_step1_complete()

        # 步骤2: 对说话时的片段进行变速，让他们的时间符合tts所对应的语音
        self.log("\n⚡ 步骤2: 变速说话片段...")
        speed_adjusted_segments = []

        for i, segment in enumerate(original_segments):
            self.log(f"\n🔄 处理片段 {i+1}/{len(original_segments)}")
            self.show_progress(i+1, len(original_segments), "调速处理")

            if segment['type'] == 'speech':
                audio = segment['audio_file']
                speed_factor = segment['duration'] / audio['new_duration']

                if abs(speed_factor - 1.0) < 0.01:  # 基本不需要调速
                    self.log(f"  说话片段 {i+1}: 无需调速 ({speed_factor:.3f}x)")
                    speed_adjusted_path = segment['path']
                    speed_factor = 1.0
                else:
                    self.log(f"  说话片段 {i+1}: 调速 {speed_factor:.2f}x ({segment['duration']:.2f}s → {audio['new_duration']:.2f}s)")
                    speed_adjusted_path = os.path.join(self.temp_dir, f"step2_speech_speed_{i}.mp4")

                    if not self.adjust_video_speed_with_audio(segment['path'], speed_factor, speed_adjusted_path):
                        self.log(f"  ❌ 调速失败，使用原片段", "ERROR")
                        speed_adjusted_path = segment['path']
                        speed_factor = 1.0

                speed_adjusted_segments.append({
                    'path': speed_adjusted_path,
                    'type': 'speech',
                    'duration': audio['new_duration'],  # 调速后的时长
                    'has_audio': True,
                    'audio_file': audio
                })
            else:
                # 间隙和尾部片段保持不变
                self.log(f"  {segment['type']}片段 {i+1}: 保持原速")
                speed_adjusted_segments.append({
                    'path': segment['path'],
                    'type': segment['type'],
                    'duration': segment['duration'],
                    'has_audio': True  # 都带有原音频
                })

        self.log(f"\n✅ 步骤2完成: 说话片段变速完成")

        # 完成第二个任务
        self.todo_write_step2_complete()

        # 步骤3: 变速后直接替换TTS音频到原视频音轨
        self.log("\n🔄 步骤3: 变速后替换TTS音频...")

        final_segments = []
        gap_audio_segments = []  # 存储间隙音频片段路径

        for i, segment in enumerate(speed_adjusted_segments):
            if segment['type'] == 'speech':
                # 对于说话片段，变速后直接替换为TTS音频
                speech_with_tts_path = os.path.join(self.temp_dir, f"step3_speech_with_tts_{i}.mp4")
                audio = segment['audio_file']

                self.log(f"  说话片段 {i+1}: 变速后替换为TTS音频 ({audio['new_duration']:.2f}s)")

                # 验证TTS音频文件是否存在
                if not os.path.exists(audio['path']):
                    self.log(f"    ❌ TTS音频文件不存在: {audio['path']}", "ERROR")
                    return False

                # 验证调速后的视频片段是否存在
                if not os.path.exists(segment['path']):
                    self.log(f"    ❌ 调速后的视频片段不存在: {segment['path']}", "ERROR")
                    return False

                if self.merge_audio_with_video(segment['path'], audio['path'], speech_with_tts_path):
                    final_segments.append(speech_with_tts_path)
                    self.log(f"    ✅ TTS音频替换完成")
                else:
                    self.log(f"    ❌ TTS音频替换失败", "ERROR")
                    return False
            else:
                # 对于间隙片段，直接使用原片段（包含原始音频）
                final_segments.append(segment['path'])
                gap_audio_segments.append(segment['path'])
                self.log(f"  {segment['type']}片段 {i+1}: 保持原样 ({segment['duration']:.2f}s)")

        self.log("✅ 步骤3完成: TTS音频替换完成")

        # 完成第三个任务
        self.todo_write_step3_complete()

        # 步骤4: 标准化所有片段并拼合（确保音频格式一致）
        self.log("\n🎬 步骤4: 标准化片段并最终拼接...")

        if final_segments:
            # 创建标准化目录
            normalized_dir = os.path.join(self.temp_dir, "normalized")
            os.makedirs(normalized_dir, exist_ok=True)

            normalized_segments = []

            # 标准化所有片段，确保音频格式统一
            self.log("  🔄 标准化所有视频片段...")
            for i, segment_path in enumerate(final_segments):
                self.show_progress(i+1, len(final_segments), "标准化片段")

                segment_name = os.path.splitext(os.path.basename(segment_path))[0]
                normalized_path = os.path.join(normalized_dir, f"{segment_name}_normalized.mp4")

                self.log(f"    标准化: {os.path.basename(segment_path)}")

                # 标准化命令：统一视频编码、音频采样率和格式
                normalize_cmd = [
                    'ffmpeg', '-y', '-i', segment_path,
                    '-c:v', 'libx264',     # 统一视频编码
                    '-preset', 'ultrafast', # 使用快速预设
                    '-crf', '30',           # 适中的质量
                    '-r', '30',             # 统一帧率
                    '-c:a', 'aac',          # 统一音频编码为AAC
                    '-ar', '22050',         # 统一音频采样率为22050Hz（与TTS音频匹配）
                    '-ac', '1',             # 单声道
                    '-b:a', '128k',         # 统一音频码率
                    '-pix_fmt', 'yuv420p',  # 统一像素格式
                    '-avoid_negative_ts', '1',
                    normalized_path
                ]

                try:
                    subprocess.run(normalize_cmd, check=True, capture_output=True)
                    normalized_segments.append(normalized_path)
                    self.log(f"    ✅ 标准化完成")
                except subprocess.CalledProcessError as e:
                    self.log(f"    ❌ 标准化失败: {e}", "ERROR")
                    return False

            # 创建标准化文件列表
            final_file_list = os.path.join(self.temp_dir, "step4_final_file_list.txt")
            with open(final_file_list, 'w') as f:
                for segment_path in normalized_segments:
                    abs_path = os.path.abspath(segment_path)
                    f.write(f"file '{abs_path}'\n")

            try:
                # 使用copy模式拼接标准化后的文件（现在格式完全一致）
                self.log("  🔧 拼接标准化后的文件...")
                cmd_concat = [
                    'ffmpeg', '-y', '-f', 'concat', '-safe', '0',
                    '-i', final_file_list,
                    '-c', 'copy',  # 使用copy模式，因为文件已标准化
                    '-movflags', '+faststart',
                    output_path
                ]
                result = subprocess.run(cmd_concat, capture_output=True, text=True)
                if result.returncode != 0:
                    # 如果copy模式失败，使用重新编码作为后备
                    self.log("  ⚠️  copy模式失败，尝试重新编码...")
                    cmd_reencode = [
                        'ffmpeg', '-y', '-f', 'concat', '-safe', '0',
                        '-i', final_file_list,
                        '-c:v', 'libx264',
                        '-preset', self.preset,
                        '-crf', '23',
                        '-c:a', 'aac',
                        '-ar', '22050',     # 确保最终输出也是22050Hz
                        '-ac', '1',
                        '-b:a', '128k',
                        '-movflags', '+faststart',
                        '-pix_fmt', 'yuv420p',
                        output_path
                    ]
                    result = subprocess.run(cmd_reencode, capture_output=True, text=True)
                    if result.returncode != 0:
                        self.log(f"  ❌ 重新编码模式也失败: {result.stderr}", "ERROR")
                        return False

                self.log("✅ 步骤4完成: 最终视频合成完成")
            except subprocess.CalledProcessError as e:
                self.log(f"❌ 最终拼接失败: {e}", "ERROR")
                return False
        else:
            self.log("❌ 没有有效的片段可拼接", "ERROR")
            return False

        # 完成第四个任务
        self.todo_write_step4_complete()

        # 显示最终文件信息
        try:
            final_size = os.path.getsize(output_path) / (1024 * 1024)  # MB
            final_info = self.get_video_info(output_path)
            final_duration = float(final_info['format']['duration'])

            # 验证音频质量
            self.validate_audio_quality(output_path)

            self.log("=" * 60)
            self.log("🎉 视频翻译处理完成!", "SUCCESS")
            self.log(f"📁 输出文件: {output_path}")
            self.log(f"📊 文件大小: {final_size:.2f} MB")
            self.log(f"⏱️  最终时长: {final_duration:.2f} 秒 ({final_duration/60:.2f} 分钟)")
            self.log(f"⏱️  处理时间: {self.get_elapsed_time()}")
            self.log(f"🚀 编码方式: {self.gpu_info['description'] if self.gpu_acceleration else 'CPU编码'}")
            self.log("=" * 60)
        except Exception as e:
            self.log(f"⚠️  获取最终文件信息失败: {e}", "WARNING")

        return True

    def validate_audio_quality(self, video_path: str):
        """验证最终视频的音频质量"""
        try:
            self.log("🔍 验证音频质量...")

            # 获取视频信息
            cmd = [
                'ffprobe', '-v', 'quiet', '-print_format', 'json',
                '-show_format', '-show_streams', video_path
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
                sample_rate = int(audio_stream.get('sample_rate', 0))
                channels = int(audio_stream.get('channels', 0))
                codec = audio_stream.get('codec_name', 'unknown')

                self.log(f"📊 音频流信息:")
                self.log(f"   编解码器: {codec}")
                self.log(f"   采样率: {sample_rate} Hz")
                self.log(f"   声道数: {channels}")

                # 验证音频质量指标
                if codec == 'aac':
                    self.log("✅ 音频编码格式正确 (AAC)")
                else:
                    self.log(f"⚠️  音频编码为 {codec}，推荐使用AAC")

                # 检查采样率是否在合理范围内
                if 16000 <= sample_rate <= 48000:
                    self.log(f"✅ 音频采样率 {sample_rate} Hz 正常")
                else:
                    self.log(f"⚠️  音频采样率 {sample_rate} Hz 可能异常")

                # 检查声道数
                if channels == 1:
                    self.log("✅ 单声道音频，适合语音内容")
                elif channels == 2:
                    self.log("ℹ️  立体声音频")
                else:
                    self.log(f"⚠️  {channels} 声道，不常见")

                # 检查音频时长是否匹配视频时长
                video_duration = float(info['format']['duration'])
                audio_duration = float(audio_stream.get('duration', 0))
                if abs(video_duration - audio_duration) < 0.5:  # 允许0.5秒误差
                    self.log(f"✅ 音频时长与视频时长匹配 (相差{abs(video_duration - audio_duration):.2f}秒)")
                else:
                    self.log(f"⚠️  音频时长({audio_duration:.2f}s)与视频时长({video_duration:.2f}s)不匹配")

            else:
                self.log("❌ 未找到音频流", "WARNING")

        except Exception as e:
            self.log(f"⚠️  音频质量验证失败: {e}", "WARNING")

    def todo_write_step1_complete(self):
        """标记步骤1完成"""
        pass

    def todo_write_step2_complete(self):
        """标记步骤2完成"""
        pass

    def todo_write_step3_complete(self):
        """标记步骤3完成"""
        pass

    def todo_write_step4_complete(self):
        """标记步骤4完成"""
        pass


def main():
    """命令行接口"""
    parser = argparse.ArgumentParser(
        description='视频翻译最后一步：将TTS音频与视频合成',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  python video_processor.py input.mp4                    # 默认GPU加速
  python video_processor.py input.mp4 --gpu cpu         # 强制CPU编码
  python video_processor.py input.mp4 -a /path/to/tts/audio
  python video_processor.py input.mp4 -o output.mp4
  python video_processor.py input.mp4 --gpu nvidia --preset fast  # 指定GPU类型和预设
        """
    )

    parser.add_argument('video_path', help='输入视频文件路径')
    parser.add_argument('-a', '--audio-dir',
                       help='TTS音频文件夹路径（默认为视频文件同目录下的tts_output文件夹）')
    parser.add_argument('-o', '--output',
                       help='输出视频文件路径（默认为视频文件同目录下的output_video.mp4）')

    # GPU加速选项
    gpu_group = parser.add_argument_group('GPU加速选项')
    gpu_group.add_argument('--gpu', nargs='?', const='auto', default='auto',
                          choices=['auto', 'nvidia', 'amd', 'intel', 'cpu'],
                          help='GPU加速类型 (默认auto=自动检测; 可选: nvidia, amd, intel, cpu)')
    gpu_group.add_argument('--preset', choices=['fast', 'medium', 'slow'], default='fast',
                          help='编码速度预设 (fast=快速/中等质量, medium=平衡, slow=高质量)')

    args = parser.parse_args()

    # 确定音频目录
    if args.audio_dir:
        audio_dir = args.audio_dir
    else:
        video_dir = os.path.dirname(args.video_path)
        audio_dir = os.path.join(video_dir, "tts_output")

    # 确定输出路径
    if args.output:
        output_path = args.output
    else:
        video_dir = os.path.dirname(args.video_path)
        video_name = os.path.splitext(os.path.basename(args.video_path))[0]
        output_path = os.path.join(video_dir, f"{video_name}_translated.mp4")

    # 检查ffmpeg是否可用
    try:
        subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("错误: 未找到 ffmpeg，请确保已安装 ffmpeg")
        exit(1)

    # 解析GPU选项
    if args.gpu == 'cpu':
        gpu_enabled = False
        gpu_type = 'cpu'
    else:
        gpu_enabled = True
        gpu_type = args.gpu if args.gpu != 'auto' else 'auto'

    if gpu_enabled:
        print("🚀 GPU加速模式已启用 (默认)")
        print(f"📊 GPU类型: {gpu_type}")
        print(f"⚡ 编码预设: {args.preset}")
        print("使用 --gpu cpu 可强制使用CPU编码")
        print()
    else:
        print("💻 使用CPU编码模式")
        print("使用 --gpu 可启用GPU加速")
        print()

    # 处理视频
    with VideoProcessor(gpu_acceleration=gpu_enabled, gpu_type=gpu_type, preset=args.preset) as processor:
        success = processor.process_video_translation(args.video_path, audio_dir, output_path)

        if success:
            print(f"\n🎉 视频翻译处理成功完成!")
            print(f"📁 输出文件: {output_path}")
            if gpu_enabled:
                print(f"🚀 使用GPU加速: {processor.gpu_info['description']}")
        else:
            print(f"\n❌ 视频翻译处理失败!")
            exit(1)


if __name__ == "__main__":
    main()