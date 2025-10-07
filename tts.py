
import json
import hashlib
import os
import time
from gradio_client import Client, file as gradio_file

def generate_text_hash(text):
    """生成文本的哈希值"""
    return hashlib.md5(text.encode('utf-8')).hexdigest()[:8]

def tts_from_translated_json(json_file_path, reference_audio_path, output_dir=None):
    """
    从翻译后的JSON文件生成TTS音频

    Args:
        json_file_path: 翻译后的JSON文件路径
        reference_audio_path: 参考音频文件路径
        output_dir: 输出目录，如果不指定则默认在翻译文件所在目录下创建tts_output文件夹
    """
    # 如果未指定输出目录，在翻译文件所在目录下创建tts_output文件夹
    if output_dir is None:
        json_dir = os.path.dirname(json_file_path)
        output_dir = os.path.join(json_dir, "tts_output")

    # 创建输出目录
    os.makedirs(output_dir, exist_ok=True)

    # 读取JSON文件
    with open(json_file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # 初始化TTS客户端
    client = Client("http://localhost:7860/")

    # 性能统计变量
    total_segments = len(data['segments'])
    total_generation_time = 0
    total_audio_duration = 0
    successful_segments = 0

    # 记录开始时间
    process_start_time = time.time()

    print(f"=== TTS性能统计开始 ===")
    print(f"总段落数: {total_segments}")

    # 处理每个段落
    for i, segment in enumerate(data['segments']):
        start_time = int(segment['start'])
        end_time = int(segment['end'])
        translated_text = segment['translated_text']
        segment_duration = (end_time - start_time) / 1000.0  # 转换为秒
        text_length = len(translated_text)

        # 生成文本哈希
        text_hash = generate_text_hash(translated_text)

        # 生成输出文件名
        output_filename = f"tts_{start_time}_{end_time}_{text_hash}.wav"
        output_path = os.path.join(output_dir, output_filename)

        print(f"\n处理第 {i+1}/{total_segments} 段: {start_time}-{end_time}ms")
        print(f"音频片段长度: {segment_duration:.2f}秒")
        print(f"翻译文本长度: {text_length} 字符")
        print(f"文本: {translated_text[:100]}...")
        print(f"输出文件: {output_filename}")

        # 记录生成开始时间
        generation_start_time = time.time()

        try:
            # 调用TTS服务
            result = client.predict(
                emo_control_method="Same as the voice reference",
                prompt=gradio_file(reference_audio_path),
                text=translated_text,
                emo_ref_path=None,
                emo_weight=0.65,
                vec1=0,
                vec2=0,
                vec3=0,
                vec4=0,
                vec5=0,
                vec6=0,
                vec7=0,
                vec8=0,
                emo_text="",
                emo_random=False,
                max_text_tokens_per_segment=120,
                param_16=True,
                param_17=0.8,
                param_18=30,
                param_19=0.8,
                param_20=0,
                param_21=3,
                param_22=10,
                param_23=1500,
                api_name="/gen_single"
            )

            # 记录生成结束时间
            generation_end_time = time.time()
            generation_time = generation_end_time - generation_start_time

            # 保存结果
            if result:
                # 从Gradio返回的字典中获取生成的音频文件路径
                generated_audio_path = result['value']

                # 复制生成的文件到输出目录
                import shutil
                shutil.copy(generated_audio_path, output_path)

                # 更新统计信息
                total_generation_time += generation_time
                total_audio_duration += segment_duration
                successful_segments += 1

                print(f"✓ 已保存: {output_filename}")
                print(f"⏱️  生成耗时: {generation_time:.2f}秒")
                print(f"📊 实时倍率: {segment_duration/generation_time:.2f}x (音频时长/生成时间)")
            else:
                print(f"✗ 生成失败: {output_filename}")

        except Exception as e:
            generation_end_time = time.time()
            generation_time = generation_end_time - generation_start_time
            print(f"✗ 处理段落时出错: {e}")
            print(f"⏱️  失败段落耗时: {generation_time:.2f}秒")
            continue

        print("-" * 60)

    # 记录总处理时间
    process_end_time = time.time()
    total_process_time = process_end_time - process_start_time

    # 计算音频总长度（最后一个片段的end时间）
    if data['segments']:
        last_segment_end = int(data['segments'][-1]['end'])
        total_asr_duration = last_segment_end / 1000.0  # 转换为秒
    else:
        total_asr_duration = 0

    # 输出性能统计
    print(f"\n" + "="*60)
    print(f"=== TTS性能统计完成 ===")
    print(f"📁 输出目录: {output_dir}")
    print(f"🎵 音频总长度: {total_asr_duration:.2f}秒 ({total_asr_duration/60:.2f}分钟)")
    print(f"⏱️  TTS生成总耗时: {total_generation_time:.2f}秒 ({total_generation_time/60:.2f}分钟)")
    print(f"📈 平均生成速度: {total_asr_duration/total_generation_time:.2f}x (实时倍率)")
    print(f"🎯 成功处理段落: {successful_segments}/{total_segments}")
    print(f"⚡ 平均每段生成时间: {total_generation_time/successful_segments:.2f}秒" if successful_segments > 0 else "⚡ 无成功段落")
    print(f"🕐 总处理时间(含IO): {total_process_time:.2f}秒")
    print("="*60)

def main():
    """
    命令行接口主函数
    """
    import argparse

    parser = argparse.ArgumentParser(description='从翻译后的JSON文件生成TTS音频')
    parser.add_argument('json_file', help='翻译后的JSON文件路径')
    parser.add_argument('reference_audio', help='参考音频文件路径')
    parser.add_argument('-o', '--output-dir', help='输出目录路径（可选，默认在JSON文件同目录下创建tts_output文件夹）')

    args = parser.parse_args()

    # 检查文件是否存在
    if not os.path.exists(args.json_file):
        print(f"错误: 找不到JSON文件 {args.json_file}")
        exit(1)

    if not os.path.exists(args.reference_audio):
        print(f"错误: 找不到参考音频文件 {args.reference_audio}")
        exit(1)

    # 开始TTS生成
    try:
        print(f"开始生成TTS音频...")
        print(f"输入JSON文件: {args.json_file}")
        print(f"参考音频文件: {args.reference_audio}")
        if args.output_dir:
            print(f"输出目录: {args.output_dir}")
        else:
            tts_output_dir = os.path.join(os.path.dirname(args.json_file), "tts_output")
            print(f"输出目录: {tts_output_dir} (在JSON文件同目录下的tts_output文件夹)")
        print("-" * 50)

        tts_from_translated_json(args.json_file, args.reference_audio, args.output_dir)
        print("TTS生成完成！")

    except Exception as e:
        print(f"TTS生成过程中发生错误: {e}")
        exit(1)


if __name__ == "__main__":
    main()
