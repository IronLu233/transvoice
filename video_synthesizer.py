#!/usr/bin/env python3
"""
视频合成脚本
基于MoviePy实现视频合成功能
"""

import argparse
import os
import sys
from pathlib import Path

from typing import Optional, List, Dict

os.environ["FFMPEG_BINARY"] = "/usr/bin/ffmpeg"
os.environ["FFPLAY_BINARY"] = "/usr/bin/ffplay"

from moviepy import VideoFileClip, AudioFileClip, concatenate_videoclips

def parse_arguments():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description="视频合成工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  python video_synthesizer.py video.mp4
  python video_synthesizer.py video.mp4 --tts-dir /path/to/tts/files
  python video_synthesizer.py video.mp4 --tts-dir ./tts_output --output final_video.mp4
        """
    )

    parser.add_argument(
        "video_file",
        type=str,
        help="输入视频文件的路径（必选）"
    )

    parser.add_argument(
        "--tts-dir", "--tts-dir",
        type=str,
        default=None,
        help="TTS语音文件目录路径（可选，默认为视频所在目录下的tts_output文件夹）"
    )

    parser.add_argument(
        "--output", "-o",
        type=str,
        default=None,
        help="输出视频文件路径（可选，默认为原文件名_synthesized.mp4）"
    )

    parser.add_argument(
        "--fps",
        type=int,
        default=24,
        help="输出视频的帧率（默认：24）"
    )

    parser.add_argument(
        "--no-gpu",
        action="store_true",
        help="禁用GPU加速编码，使用CPU编码"
    )


    parser.add_argument(
        "--debug-export",
        action="store_true",
        help="导出每个带音频的视频片段用于调试"
    )

    return parser.parse_args()

def validate_inputs(video_file: str, tts_dir: Optional[str] = None) -> bool:
    """验证输入参数"""
    # 检查视频文件是否存在
    if not os.path.exists(video_file):
        print(f"错误: 视频文件不存在: {video_file}")
        return False

    # 检查视频文件扩展名
    video_extensions = ['.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv', '.webm', '.m4v']
    if not any(video_file.lower().endswith(ext) for ext in video_extensions):
        print(f"警告: 文件可能不是视频文件: {video_file}")

    # 确定TTS目录路径
    if tts_dir is None:
        # 默认使用视频文件所在目录下的tts_output
        video_path = Path(video_file)
        tts_dir = video_path.parent / "tts_output"

    # 检查TTS目录是否存在
    if os.path.exists(tts_dir):
        print(f"使用TTS目录: {tts_dir}")
    else:
        print(f"警告: TTS目录不存在: {tts_dir}")

    return True

def find_tts_files(tts_dir: str) -> List[str]:
    """查找TTS目录中的所有音频文件"""
    if not os.path.exists(tts_dir):
        return []

    audio_extensions = ['.wav', '.mp3', '.m4a', '.aac']
    tts_files = []

    for ext in audio_extensions:
        tts_files.extend(Path(tts_dir).glob(f"*{ext}"))

    # 按文件名排序
    tts_files.sort(key=lambda x: x.name)
    return [str(f) for f in tts_files]

def parse_tts_filename(tts_filename: str) -> Optional[Dict]:
    """
    从TTS文件名中解析出音频对应原视频的时间信息

    文件名格式: tts_{start_time}_{end_time}_{hash}.wav
    时间单位: 毫秒

    Args:
        tts_filename: TTS文件名

    Returns:
        包含时间信息的字典，格式：
        {
            'start_time_ms': int,    # 开始时间（毫秒）
            'end_time_ms': int,      # 结束时间（毫秒）
            'start_time_s': float,   # 开始时间（秒）
            'end_time_s': float,     # 结束时间（秒）
            'duration': float,       # 持续时间（秒）
            'hash': str             # 文件哈希值
        }
        如果解析失败返回None
    """
    import re

    # 提取文件名（去掉路径和扩展名）
    filename = Path(tts_filename).stem

    # 使用正则表达式匹配文件名格式
    pattern = r'tts_(\d+)_(\d+)_([a-f0-9]+)'
    match = re.match(pattern, filename)

    if not match:
        print(f"警告: 无法解析TTS文件名格式: {tts_filename}")
        return None

    try:
        start_time_ms = int(match.group(1))
        end_time_ms = int(match.group(2))
        file_hash = match.group(3)

        # 转换为秒
        start_time_s = start_time_ms / 1000.0
        end_time_s = end_time_ms / 1000.0
        duration = end_time_s - start_time_s

        return {
            'start_time_ms': start_time_ms,
            'end_time_ms': end_time_ms,
            'start_time_s': start_time_s,
            'end_time_s': end_time_s,
            'duration': duration,
            'hash': file_hash
        }

    except (ValueError, IndexError) as e:
        print(f"警告: 解析TTS文件名时出错 {tts_filename}: {e}")
        return None

def validate_time_ranges(tts_files: List[str], video_duration: float) -> List[str]:
    """
    验证TTS文件的时间范围是否在视频时长内

    Args:
        tts_files: TTS文件列表
        video_duration: 视频总时长（秒）

    Returns:
        过滤后的TTS文件列表（只包含时间范围有效的文件）
    """
    valid_files = []

    for tts_file in tts_files:
        time_info = parse_tts_filename(tts_file)
        if not time_info:
            print(f"跳过无法解析的文件: {tts_file}")
            continue

        if time_info['start_time_s'] >= video_duration:
            print(f"⚠️  警告: 文件 {Path(tts_file).name} 的开始时间 ({time_info['start_time_s']:.2f}s) 超过视频总时长 ({video_duration:.2f}s)，跳过")
            continue

        if time_info['end_time_s'] > video_duration:
            print(f"⚠️  警告: 文件 {Path(tts_file).name} 的结束时间 ({time_info['end_time_s']:.2f}s) 超过视频总时长 ({video_duration:.2f}s)，跳过")
            continue

        valid_files.append(tts_file)

    return valid_files


def get_audio_duration(audio_file: str) -> float:
    """获取音频文件的时长"""
    try:
        with AudioFileClip(audio_file) as audio_clip:
            return audio_clip.duration
    except Exception as e:
        print(f"警告: 无法获取音频时长 {audio_file}: {e}")
        return 0.0

def cleanup_invalid_cache(segment_dir: Path, valid_tts_files: List[str]) -> None:
    """
    清理失效的缓存文件，只保留当前TTS文件列表中有效的片段

    Args:
        segment_dir: 片段存储目录
        valid_tts_files: 当前有效的TTS文件列表
    """
    if not segment_dir.exists():
        return

    # 创建当前TTS文件对应的片段文件名集合
    expected_segments = set()
    for i, tts_file in enumerate(valid_tts_files):
        segment_filename = f"segment_{i+1:02d}_{Path(tts_file).stem}.mp4"
        expected_segments.add(segment_filename)

    # 检查现有片段文件，删除不在期望集合中的文件
    deleted_count = 0
    for segment_file in segment_dir.glob("segment_*.mp4"):
        if segment_file.name not in expected_segments:
            try:
                segment_file.unlink()
                print(f"  🗑️  删除失效缓存: {segment_file.name}")
                deleted_count += 1
            except Exception as e:
                print(f"  ⚠️  删除缓存文件失败 {segment_file.name}: {e}")

    if deleted_count > 0:
        print(f"  ✅ 清理完成，删除了 {deleted_count} 个失效缓存文件")
    else:
        print(f"  ✅ 没有需要清理的失效缓存")

def synthesize_video_with_tts(video_file: str, tts_dir: str, output_file: str, use_gpu: bool = False, debug_export: bool = False):
    """
    使用TTS音频合成视频 - 根据音频时长动态调整视频片段速度

    Args:
        video_file: 原视频文件路径
        tts_dir: TTS音频文件目录路径
        output_file: 输出视频文件路径
        debug_export: 是否导出每个片段用于调试

    Returns:
        bool: 是否成功
    """

    # 在函数内部查找TTS文件
    tts_files = find_tts_files(tts_dir)
    print(f"在目录 {tts_dir} 中找到 {len(tts_files)} 个TTS文件")

    print(f"\n🎬 开始视频合成")
    print(f"原视频: {video_file}")
    print(f"TTS文件数量: {len(tts_files)}")
    print(f"输出文件: {output_file}")

    # 加载原视频
    with VideoFileClip(video_file) as video_clip:
        video_duration = video_clip.duration
        print(f"原视频时长: {video_duration:.2f}s")

        # 验证TTS文件的时间范围
        valid_tts_files = validate_time_ranges(tts_files, video_duration)
        print(f"过滤后的有效TTS文件: {len(valid_tts_files)} 个")

        if not valid_tts_files:
            print("❌ 没有有效的TTS文件")
            return False

        output_path = Path(output_file)
        segment_dir = output_path.parent / "segments"
        segment_dir.mkdir(exist_ok=True)

        for i, tts_file in enumerate(valid_tts_files):
            print(f"\n📁 处理第 {i+1}/{len(valid_tts_files)} 个TTS文件: {Path(tts_file).name}")

            # 解析TTS文件名中的时间信息
            time_info = parse_tts_filename(tts_file)
            if not time_info:
                print(f"跳过无法解析的文件: {tts_file}")
                continue

            # 获取TTS音频时长
            tts_duration = get_audio_duration(tts_file)
            if tts_duration <= 0:
                print(f"跳过无效的音频文件: {tts_file}")
                continue

            print(f"  📽️  原视频片段: {time_info['start_time_s']:.2f}s - {time_info['end_time_s']:.2f}s (时长: {time_info['duration']:.2f}s)")
            print(f"  🔊 TTS音频时长: {tts_duration:.2f}s")

            # 提取对应的视频片段
            video_segment = video_clip.subclipped(time_info['start_time_s'], time_info['end_time_s'])

            # 计算速度调整因子：音频时长 / 原视频片段时长
            speed_factor = time_info['duration'] / tts_duration
            print(f"  ⚙️  速度调整因子: {speed_factor:.2f}x")

            if speed_factor > 1.0:
                print(f"      🚀 原视频片段比音频长，需要加速 {speed_factor:.2f}x")
            elif speed_factor < 1.0:
                print(f"      🐌 原视频片段比音频短，需要减速到 {speed_factor:.2f}x 原速度")
            else:
                print(f"      ✅ 原视频片段时长与音频匹配，无需调速")

            # 调整视频速度以匹配TTS音频时长
            if abs(speed_factor - 1.0) > 0.01:  # 只有在速度差异较大时才调整
                adjusted_segment = video_segment.with_speed_scaled(speed_factor)
                print(f"      ✨ 视频片段已调整至 {adjusted_segment.duration:.2f}s")
            else:
                adjusted_segment = video_segment
                print(f"      ✨ 视频片段保持原时长 {adjusted_segment.duration:.2f}s")

            # 加载TTS音频
            try:
                tts_audio = AudioFileClip(tts_file)
                print(f"      🔊 TTS音频加载成功，时长: {tts_audio.duration:.2f}s，采样率: {tts_audio.fps}Hz")

                # 确保音频时长与调整后的视频时长完全匹配
                if abs(tts_audio.duration - adjusted_segment.duration) > 0.1:
                    # 微调音频时长以匹配视频
                    tts_audio = tts_audio.with_duration(adjusted_segment.duration)
                    print(f"      ✂️  音频时长已微调至 {tts_audio.duration:.2f}s")

                # 将音频设置到视频片段上
                final_segment = adjusted_segment.with_audio(tts_audio)

                # 检查音频是否成功附加
                if final_segment.audio is not None:
                    print(f"      ✅ 音频成功附加到视频片段，音频时长: {final_segment.audio.duration:.2f}s")
                else:
                    print(f"      ❌ 警告：音频附加失败，视频片段无音频轨道")

                # 导出带音频的视频片段到磁盘（必须写入磁盘，否则后续合成会丢失音频）
                segment_filename = f"segment_{i+1:02d}_{Path(tts_file).stem}.mp4"
                segment_path = segment_dir / segment_filename

                # 检查缓存：如果片段文件已存在且有效，则跳过生成
                if segment_path.exists():
                    print(f"      💾 片段文件已存在，跳过生成: {segment_path}")
                    # 验证现有文件的有效性（检查文件大小和基本完整性）
                    if segment_path.stat().st_size > 0:
                        print(f"      ✅ 使用缓存的片段文件: {segment_path}")
                        continue
                    else:
                        print(f"      ⚠️  缓存文件无效，重新生成: {segment_path}")

                try:
                    final_segment.write_videofile(
                        str(segment_path),
                        fps=24,
                        codec="h264_nvenc",
                        preset="fast",
                        audio=True,
                        pixel_format="yuv420p"
                    )
                    print(f"      ✅ 视频片段导出成功: {segment_path}")
                except Exception as export_error:
                    print(f"      ❌ 视频片段导出失败: {export_error}")
                    continue

                tts_audio.close()

            except Exception as e:
                print(f"      ❌ 处理TTS文件时出错: {e}")
                continue

        # 清理视频片段内存
        video_segment.close()
        if 'adjusted_segment' in locals():
            adjusted_segment.close()
        if 'final_segment' in locals():
            final_segment.close()

    # 第二步：用保存的片段替换原视频对应部分
    print(f"\n🎬 第二步：用保存的片段替换原视频对应部分")

    # 重新加载原视频
    try:
        with VideoFileClip(video_file) as original_video:
            video_duration = original_video.duration
            print(f"📹 原视频时长: {video_duration:.2f}s")

            # 查找所有导出的视频片段文件
            segment_files = sorted(segment_dir.glob("segment_*.mp4"))

            if not segment_files:
                print(f"❌ 没有找到导出的视频片段文件")
                return False

            print(f"📁 找到 {len(segment_files)} 个视频片段文件")

            # 解析每个片段的时间信息并加载
            segments_info = []
            import re
            for seg_file in segment_files:
                try:
                    # 从文件名提取TTS文件名：segment_XX_tts_12345678_12345678_hash.mp4
                    match = re.match(r"segment_\d+_(tts_\d+_\d+_[a-f0-9]+)\.mp4", seg_file.name)
                    if match:
                        tts_filename = match.group(1)
                        time_info = parse_tts_filename(tts_filename + ".wav")
                        if time_info:
                            clip = VideoFileClip(str(seg_file))
                            segments_info.append({
                                'clip': clip,
                                'start_time': time_info['start_time_s'],
                                'end_time': time_info['end_time_s'],
                                'duration': clip.duration,
                                'file': seg_file
                            })
                            print(f"  📹 加载片段: {seg_file.name}")
                            print(f"     📽️  替换时间: {time_info['start_time_s']:.2f}s - {time_info['end_time_s']:.2f}s")
                            print(f"     🎵 片段时长: {clip.duration:.2f}s")
                except Exception as e:
                    print(f"  ❌ 处理片段失败 {seg_file.name}: {e}")
                    continue

            if not segments_info:
                print(f"❌ 没有成功加载任何视频片段")
                return False

            # 按时间顺序排序片段
            segments_info.sort(key=lambda x: x['start_time'])
            print(f"✅ 成功加载 {len(segments_info)} 个有效片段")

            # 创建最终视频：原视频片段 + 替换的音频片段
            print(f"\n🔗 开始创建最终视频...")

            # 构建最终的片段列表
            final_clips = []
            current_time = 0

            for seg_info in segments_info:
                seg_start = seg_info['start_time']
                seg_end = seg_info['end_time']

                # 添加当前片段之前的原视频部分（静音处理）
                if current_time < seg_start:
                    original_part = original_video.subclipped(current_time, seg_start)
                    # 静音处理：移除原视频的音频
                    original_part = original_part.without_audio()
                    final_clips.append(original_part)
                    print(f"  ➕ 添加原视频片段（已静音）: {current_time:.2f}s - {seg_start:.2f}s")

                # 添加带新音频的片段（替换原视频的对应部分）
                # 确保片段没有alpha通道问题，设置背景色为黑色
                if hasattr(seg_info['clip'], 'mask') and seg_info['clip'].mask is not None:
                    seg_clip = seg_info['clip']
                    seg_clip = seg_clip.without_audio()  # 先移除音频
                    seg_clip = seg_clip.with_mask(False)  # 移除mask，会填充黑色背景
                    seg_clip = seg_clip.with_audio(seg_info['clip'].audio)  # 重新添加音频
                    final_clips.append(seg_clip)
                else:
                    final_clips.append(seg_info['clip'])
                print(f"  🔄 替换原视频片段: {seg_start:.2f}s - {seg_end:.2f}s (新片段时长: {seg_info['duration']:.2f}s)")

                current_time = seg_end

            # 添加最后一个片段之后的所有原视频内容（静音处理）
            if current_time < video_duration:
                remaining_part = original_video.subclipped(current_time, video_duration)
                # 静音处理：移除原视频的音频
                remaining_part = remaining_part.without_audio()
                final_clips.append(remaining_part)
                print(f"  ➕ 添加剩余原视频（已静音）: {current_time:.2f}s - {video_duration:.2f}s")

            # 合并所有片段
            final_video = concatenate_videoclips(final_clips)
            print(f"✅ 视频片段替换完成，最终视频时长: {final_video.duration:.2f}s")

            # 导出最终视频
            print(f"📤 开始导出最终视频: {output_file}")
            final_video.write_videofile(
                output_file,
                codec="h264_nvenc",
                preset="fast",
                fps=24,
                audio=True,
                pixel_format="yuv420p"
            )

            final_video.close()

            # 清理内存
            for clip in final_clips:
                try:
                    clip.close()
                except:
                    pass

            for seg_info in segments_info:
                try:
                    seg_info['clip'].close()
                except:
                    pass

            print(f"✅ 最终视频替换成功: {output_file}")

            # 清理失效的缓存文件
            if not debug_export:
                print(f"\n🧹 清理失效的缓存文件...")
                cleanup_invalid_cache(segment_dir, valid_tts_files)
            else:
                print(f"\n💾 调试模式：保留所有片段文件: {segment_dir}")

            return True

    except Exception as e:
        print(f"❌ 视频片段替换时出错: {e}")
        return False


def main():
    """主函数"""
    # 解析命令行参数
    args = parse_arguments()

    # 验证输入参数
    if not validate_inputs(args.video_file, args.tts_dir):
        sys.exit(1)

    # 确定最终的TTS目录
    if args.tts_dir is None:
        video_path = Path(args.video_file)
        tts_dir = video_path.parent / "tts_output"
    else:
        tts_dir = args.tts_dir

    # 查找TTS文件
    tts_files = find_tts_files(tts_dir)
    print(f"找到 {len(tts_files)} 个TTS文件")

    # 获取视频时长并验证TTS文件的时间范围
    try:
        with VideoFileClip(args.video_file) as video_clip:
            video_duration = video_clip.duration
            print(f"视频时长: {video_duration:.2f}s")

            # 验证TTS文件时间范围
            valid_tts_files = validate_time_ranges(tts_files, video_duration)
            tts_files = valid_tts_files
            print(f"时间范围验证后的有效TTS文件: {len(tts_files)} 个")

    except Exception as e:
        print(f"警告: 无法获取视频时长: {e}")

    # 显示TTS文件解析信息（用于调试）
    if tts_files:
        print("\n📋 TTS文件时间信息示例:")
        for i, tts_file in enumerate(tts_files[:5]):  # 显示前5个文件的解析结果
            time_info = parse_tts_filename(tts_file)
            audio_duration = get_audio_duration(tts_file)
            if time_info:
                speed_factor = time_info['duration'] / audio_duration if audio_duration > 0 else 0
                print(f"  {i+1}. {Path(tts_file).name}")
                print(f"     📽️  原视频时间: {time_info['start_time_s']:.2f}s - {time_info['end_time_s']:.2f}s (片段时长: {time_info['duration']:.2f}s)")
                print(f"     🔊 音频时长: {audio_duration:.2f}s")
                print(f"     ⚙️  需要调速: {speed_factor:.2f}x ({'加速' if speed_factor > 1 else '减速' if speed_factor < 1 else '无需调速'})")
        if len(tts_files) > 5:
            print(f"  ... 还有 {len(tts_files) - 5} 个文件")

    # 确定输出文件路径
    if args.output is None:
        video_path = Path(args.video_file)
        args.output = video_path.parent / f"{video_path.stem}_synthesized.mp4"

    print(f"\n输入视频: {args.video_file}")
    print(f"TTS目录: {tts_dir}")
    print(f"输出视频: {args.output}")
    print(f"输出帧率: {args.fps}")
    print(f"GPU加速: {'启用' if not args.no_gpu else '禁用'}")


    print(f"\n🎬 开始使用 {len(tts_files)} 个有效TTS文件进行视频合成")
    print("📝 处理逻辑：根据音频时长动态调整视频片段速度")
    success = synthesize_video_with_tts(
        video_file=args.video_file,
        tts_dir=tts_dir,
        output_file=args.output,
        use_gpu=not args.no_gpu,
        debug_export=args.debug_export
    )

    if success:
        print(f"\n🎉 视频合成完成！输出文件: {args.output}")
        sys.exit(0)
    else:
        print(f"\n❌ 视频合成失败！")
        sys.exit(1)

if __name__ == "__main__":
    main()
