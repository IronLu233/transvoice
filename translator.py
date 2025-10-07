import dashscope
from http import HTTPStatus
import json
import time
import os
from typing import List, Dict, Optional
from config import get_api_key

def find_largest_gap(segments: List[dict]) -> tuple[int, int]:
    """
    找到segments中时间间隔最大的位置

    Args:
        segments: segment列表

    Returns:
        tuple[int, int]: (最大间隔大小, 分割点索引)
    """
    if len(segments) < 2:
        return (0, -1)

    max_gap = 0
    split_index = -1

    for i in range(1, len(segments)):
        gap = segments[i]["start"] - segments[i-1]["end"]
        if gap > max_gap:
            max_gap = gap
            split_index = i

    return (max_gap, split_index)




def split_segments_recursively(segments: List[dict], max_segment_size) -> List[List[dict]]:
    """
    递归分割segments，确保每段长度不超过max_segment_size

    Args:
        segments: 待分割的segment列表
        max_segment_size: 每段的最大长度

    Returns:
        List[List[dict]]: 分割后的chunks列表
    """
    # 基础情况：如果长度小于等于max_segment_size，直接返回
    if len(segments) <= max_segment_size:
        return [segments]

    print(f"当前segment长度: {len(segments)}, 超过最大限制 {max_segment_size}，需要分割")

    # 找到时间间隔最大的位置
    max_gap, split_index = find_largest_gap(segments)

    if split_index == -1:
        # 如果找不到合适的分割点（理论上不应该发生），强制从中间分割
        split_index = len(segments) // 2
        print(f"未找到合适的时间间隙，强制从中间位置 {split_index} 分割")
    else:
        print(f"找到最大时间间隙: {max_gap}ms，在索引 {split_index} 处分割")

    # 分割成两段
    left_part = segments[:split_index]
    right_part = segments[split_index:]

    print(f"分割为: 左段 {len(left_part)} 个segments, 右段 {len(right_part)} 个segments")

    # 递归处理两段
    left_chunks = split_segments_recursively(left_part, max_segment_size)
    right_chunks = split_segments_recursively(right_part, max_segment_size)

    # 合并结果，直接返回，不进行额外合并
    all_chunks = left_chunks + right_chunks
    return all_chunks


def merge_segments_with_qwen_max(segments: List[dict], api_key: str, max_segment_size: int = 150) -> List[dict]:
    """
    使用qwen-turbo对segments进行语义合并，返回合并后的段落
    为防止超时，使用递归分割算法将大段分割成小段

    Args:
        segments: 待合并的segment列表
        api_key: DashScope API密钥
        max_segment_size: 每段的最大长度，默认200

    Returns:
        List[dict]: 合并后的段落列表
    """
    if not segments:
        return []

    print(f"使用qwen-turbo对{len(segments)}个segments进行语义合并...")
    print(f"最大段长度限制: {max_segment_size}")

    # 使用递归分割算法分割segments
    chunks = split_segments_recursively(segments, max_segment_size)

    print(f"递归分割完成，总共分成{len(chunks)}个chunk: {[len(chunk) for chunk in chunks]}")

    # 处理每个chunk
    all_merged_segments = []
    for i, chunk in enumerate(chunks):
        print(f"处理第{i+1}/{len(chunks)}个chunk，包含{len(chunk)}个segments...")
        chunk_merged = merge_single_chunk_with_qwen_turbo(chunk, api_key)
        all_merged_segments.extend(chunk_merged)

        # 如果不是最后一个chunk，添加延迟以避免API限速
        if i < len(chunks) - 1:
            print("等待10秒后处理下一个chunk...")
            time.sleep(10)

    print(f"语义合并完成，原来{len(segments)}个segments合并为{len(all_merged_segments)}个段落")
    return all_merged_segments


def merge_single_chunk_with_qwen_turbo(segments: List[dict], api_key: str) -> List[dict]:
    """
    对单个chunk的segments进行语义合并
    """
    # 构建输入数据，只包含qwen-turbo需要的字段
    input_data = []
    for segment in segments:
        input_data.append({
            "start": int(round(segment["start"])),
            "end": int(round(segment["end"])),
            "text": segment["text"]
        })

    # 构建系统提示词
    system_prompt = """你是一个专业的多模态视频字幕分段引擎。输入是一个包含双语文本和时间戳的句子数组，每个元素格式如下：
{
  "start": 整数（毫秒）,
  "end": 整数（毫秒）,
  "text": "英文原文",
}

请根据以下规则，判断应在哪些句子处**开始新段落**：

【核心规则】
1. **视觉指代优先**：如果某句（英文或中文）隐含对视频画面的指代（例如：提及具体工具如"Killzone"、价格水平如"50 level"、图表类型如"日线图"、货币对如"欧元/美元"、时间框架如"30分钟图"、操作指令如"屏幕截图""按下Y键"等），则该句必须作为新段落的**第一句**。
2. **时间间隔辅助**：若当前句的 start 与前一句的 end 间隔 ≥ 1500 毫秒（1.5秒），且语义非紧密衔接，则可作为新段落起点。
3. **语义逻辑分段**：当话题发生明显转换（如开始讨论新的心理障碍、新教学模块、总结性陈述等），应开启新段落。
4. **第一句永远是段落起点**。
5. **段落长度控制**：分段不宜过短，除非在时间上间隔过长，原则上一个段落至少要包含完整的3句话。对于可分可不分，不触发条件1，2的段落，尽量不分段。


【输出要求】
- 仅输出一个 JSON 对象
- 包含字段 "paragraph_starts"，值为**严格递增的整数数组**，表示"每个段落起始句子的索引"
- 第一个元素必须是 0
- 不要解释，不要输出原文，不要额外字段，不要 Markdown

输出：
{"paragraph_starts": [0, 1]}

【现在处理用户提供的完整输入】"""

    try:
        dashscope.api_key = api_key

        # 调用qwen-turbo
        response = dashscope.Generation.call(
            model='qwen3-max',
            messages=[
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': json.dumps(input_data, ensure_ascii=False)}
            ],
            response_format={"type": "json_object"}  # 指定返回JSON格式
        )

        if response.status_code == HTTPStatus.OK:
            result = json.loads(response.output.choices[0].message.content)
            paragraph_starts = result.get('paragraph_starts', [0])

            print(f"qwen-turbo返回的段落起始索引: {paragraph_starts}")

            # 添加20秒延迟以避免API限速
            time.sleep(20)

            # 根据paragraph_starts合并segments
            merged_segments = []

            for i, start_idx in enumerate(paragraph_starts):
                # 确定段落的结束索引
                if i < len(paragraph_starts) - 1:
                    end_idx = paragraph_starts[i + 1]
                else:
                    end_idx = len(segments)

                # 合并这个段落的所有segments
                paragraph_segments = segments[start_idx:end_idx]
                if not paragraph_segments:
                    continue

                # 合并文本和时间戳
                merged_text = " ".join([seg["text"] for seg in paragraph_segments])
                merged_start = int(round(paragraph_segments[0]["start"]))
                merged_end = int(round(paragraph_segments[-1]["end"]))

                merged_segment = {
                    "start": merged_start,
                    "end": merged_end,
                    "text": merged_text,
                    "original_segments": paragraph_segments  # 保留原始segments信息
                }

                merged_segments.append(merged_segment)

            return merged_segments

        else:
            print(f"qwen-turbo调用失败: {response.message}")
            # 如果qwen-turbo失败，返回原始segments（不合并）
            return segments

    except Exception as e:
        print(f"qwen-turbo处理异常: {str(e)}")
        # 如果处理失败，返回原始segments（不合并）
        return segments


def try_translation(messages, api_key: str):
    """尝试翻译，支持重试"""
    try:
        dashscope.api_key = api_key
        response = dashscope.Generation.call(
            model='qwen-mt-turbo',
            messages=messages,
        )

        if response.status_code == HTTPStatus.OK:
            response_content = response.output.choices[0].message.content
            # 添加1秒延迟以避免API限速
            time.sleep(1)
            return response_content, None
        else:
            error_message = f"Error: {response.message}"
            return None, error_message
    except Exception as e:
        error_message = f"Exception: {str(e)}"
        return None, error_message


def translate_merged_paragraphs(merged_segments: List[dict], api_key: str) -> List[dict]:
    """
    直接翻译合并后的段落，不再分段批量翻译
    """
    if not api_key:
        raise ValueError("DASHSCOPE_API_KEY is not set.")

    all_translated_segments = []

    # 翻译提示模板（针对段落翻译优化）
    prompt_template = """
将以下英文段落翻译成自然流畅的中文。

ICT核心术语对照：
AMD (Accumulation, Manipulation, Distribution) = AMD模型
PO3 (Power of Three) = Power of three模型
power three = Power of three模型
BISI (Buy Side Imbalance Sell Side Inefficiency) = 买方失衡卖方低效
SIBI (Sell Side Imbalance Buy Side Inefficiency) = 卖方失衡买方低效
BPR (Balanced Price Range) = 平衡价格区间
BSL (Buy Side Liquidity) = 买方流动性
SSL (Sell Side Liquidity) = 卖方流动性
BE (Breakeven) = 盈亏平衡
BOS (Break of Structure) = 结构突破
CE (Consequent Encroachment) = FVG中点
FVG (Fair Value Gap) = 公允价值缺口
IFVG (Inversion Fair Value Gap) = 反转公允价值缺口
HTF (Higher Time Frame) = 高时间框架
LTF (Lower Time Frame) = 低时间框架
IPDA (Inter Bank Price Delivery Algorithm) = 银行间价格传递算法
STH (Short Term High) = 短期高点
ITH (Intermediate Term High) = 中期高点
LTH (Long Term High) = 长期高点
STL (Short Term Low) = 短期低点
ITL (Intermediate Term Low) = 中期低点
LTL (Long Term Low) = 长期低点
MSS (Market Structure Shift) = 市场结构转变
MT (Mean Threshold) = 订单块中点
OB (Order Block) = 订单块
OTE (Optimal Trade Entry) = 最佳交易入场
PDL (Previous Day Low) = 前一日低点
PDH (Previous Day High) = 前一日高点
ERL (External Range Liquidity) = 外部流动性
IRL (Internal Range Liquidity) = 内部流动性
PD Array (Premium & Discount Array) = PD阵列
BB (Breaker Block) = 突破块
MB (Mitigation Block) = 缓解块
NWOG (New Week Opening Gap) = 新周开盘缺口
LP (Liquidity Pool) = 流动性池
TGIF (Thanks God It's Friday) = TGIF
KZ(Kill Zone) = Kill Zone
Asia kill zone = 亚洲Kill Zone
NewYork ill zone = 纽约Kill Zone
London kill zone = 伦敦Kill zone

传统交易术语对照：
Silver Bullet = 银弹
Lot = 手
Spread = 点差
Margin = 保证金
Leverage = 杠杆
Bid = 买价
Ask = 卖价
Swap = 隔夜利息
Long = 多头
Short = 空头
Stop Loss = 止损
Take Profit = 止盈
pip = pip
pips = pips
handle = handle
tick = tick
point = 点
Draw on liquidity = 利用流动性
liquidity pool(或者拼错成 poll, polls) = 流动性池
swing = 波段
swing points = 摆动点
session = 时段
liquidity = 流动性
probability = 概率
smart money = 聪明钱
liquidity raid = 流动性突袭
stop hunt = 止损猎杀
retail = 散户
institutional = 机构
price = 价格
up close candle = 阳线
bias = 市场偏见
day trade = 日内交易
journaling = 交易日志

要求：
- 翻译整个段落，保持语义连贯
- 保持ICT专业术语准确性
- 避免生硬直译
- 确保ICT概念翻译的专业性和准确性
- 数字用大写的中文表示：零、壹、贰、叁、肆、伍、陆、柒、捌、玖、拾、佰、仟、万、亿
- 尽量保证翻译后的中文阅读时长与英文原文一致，可通过调整语言简洁程度来实现
- Ok, Okay尽量翻译成"好"，而不是"好的"
- 翻译货币对时，比如EUR/USD，中间的斜杠(/)翻译成“兑”，举例说：“EUR/USD”翻译成欧元兑美元

英文段落：
{original_text}

中文翻译：
"""

    # 逐个段落翻译
    for para_idx, merged_segment in enumerate(merged_segments):
        print(f"翻译段落 {para_idx + 1}/{len(merged_segments)}，长度: {len(merged_segment['text'])} 字符...")

        final_prompt = prompt_template.format(original_text=merged_segment['text'])
        messages = [{'role': 'user', 'content': final_prompt}]

        # 翻译段落
        response_content, error = try_translation(messages, api_key)

        if response_content:
            translated_text = response_content.strip()
            print(f"段落 {para_idx + 1} 翻译成功")

            # 创建翻译后的segment，保留原始的时间戳信息
            all_translated_segments.append({
                "start": merged_segment["start"],
                "end": merged_segment["end"],
                "original_text": merged_segment["text"],
                "translated_text": translated_text,
                "original_segments": merged_segment.get("original_segments", [])  # 保留原始segments信息
            })
        else:
            print(f"段落 {para_idx + 1} 翻译失败: {error}")
            # 创建错误条目
            all_translated_segments.append({
                "start": merged_segment["start"],
                "end": merged_segment["end"],
                "original_text": merged_segment["text"],
                "translated_text": f"[翻译错误: {error}]",
                "original_segments": merged_segment.get("original_segments", [])
            })

        # 添加延迟以避免API限速
        time.sleep(1)

    return all_translated_segments


def translate_asr_results(asr_file_path: str, api_key: Optional[str] = None, output_path: Optional[str] = None, enable_preprocessing: bool = True) -> str:
    """
    翻译ASR结果文件的主函数，增加qwen-turbo前处理步骤

    Args:
        asr_file_path (str): ASR结果JSON文件路径
        api_key (Optional[str]): DashScope API密钥，如果不提供则从配置中获取
        output_path (Optional[str]): 输出文件路径，如果不指定则自动生成
        enable_preprocessing (bool): 是否启用qwen-turbo前处理，默认启用

    Returns:
        str: 翻译结果文件的路径
    """
    print(f"开始翻译ASR结果文件: {asr_file_path}")

    # 获取API密钥
    if api_key is None:
        api_key = get_api_key()
        if not api_key:
            raise ValueError("未提供API密钥，请通过参数传入或设置环境变量 DASHSCOPE_API_KEY")

    # 检查输入文件是否存在
    if not os.path.exists(asr_file_path):
        raise FileNotFoundError(f"ASR结果文件不存在: {asr_file_path}")

    # 生成输出文件路径
    if output_path is None:
        # 获取ASR文件的目录和文件名
        asr_dir = os.path.dirname(asr_file_path)
        asr_filename = os.path.basename(asr_file_path)

        # 如果ASR文件名中包含 "asr_results"，则创建对应的翻译文件名
        if "asr_results" in asr_filename:
            # 例如：asr_results.json -> translated_results.json
            translated_filename = asr_filename.replace("asr_results", "translated_results")
        else:
            # 否则使用传统的命名方式
            base_name = os.path.splitext(asr_filename)[0]
            translated_filename = f"{base_name}_translated.json"

        output_path = os.path.join(asr_dir, translated_filename)

    # 读取ASR结果
    print("读取ASR结果...")
    with open(asr_file_path, 'r', encoding='utf-8') as f:
        asr_data = json.load(f)

    # 提取segments
    segments = asr_data.get('segments', [])
    if not segments:
        print("警告: ASR结果中没有找到segments")
        # 创建空的翻译结果
        translated_result = {
            "total_segments": 0,
            "segments": [],
            "translation_info": {
                "source_file": asr_file_path,
                "translation_model": "qwen-turbo + qwen-mt-turbo",
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
            }
        }
    else:
        print(f"找到 {len(segments)} 个segments...")

        # 第一步：使用qwen-turbo进行语义合并前处理
        if enable_preprocessing:
            print("启用qwen-turbo语义合并前处理...")
            # 使用默认最大段长度200，可以根据需要调整
            merged_segments = merge_segments_with_qwen_max(segments, api_key)
        else:
            print("跳过语义合并前处理，直接翻译...")
            merged_segments = segments  # 不进行合并，直接翻译

        # 第二步：翻译合并后的段落
        print("开始翻译...")
        translated_segments = translate_merged_paragraphs(merged_segments, api_key)

        # 构建翻译结果
        translated_result = {
            "total_segments": len(translated_segments),
            "segments": translated_segments,
            "translation_info": {
                "source_file": asr_file_path,
                "translation_model": "qwen-turbo + qwen-mt-turbo",
                "preprocessing_enabled": enable_preprocessing,
                "original_segment_count": len(segments),
                "merged_segment_count": len(merged_segments),
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
            }
        }

    # 保存翻译结果
    print(f"保存翻译结果到: {output_path}")
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(translated_result, f, ensure_ascii=False, indent=2)

    print("翻译完成!")
    return output_path


def main():
    """
    命令行接口主函数
    """
    import argparse
    from config import get_api_key

    parser = argparse.ArgumentParser(description='翻译ASR结果文件')
    parser.add_argument('asr_file', help='ASR结果JSON文件路径')
    parser.add_argument('-o', '--output', help='输出文件路径（可选，默认使用ASR文件同目录）')
    parser.add_argument('--no-preprocessing', action='store_true', help='跳过语义合并前处理')

    args = parser.parse_args()

    # 获取API密钥
    api_key = get_api_key()
    if not api_key:
        print("错误：未找到 DASHSCOPE_API_KEY，请设置环境变量或在 .env 文件中配置")
        exit(1)

    try:
        print(f"开始翻译ASR结果文件: {args.asr_file}")
        output_file = translate_asr_results(args.asr_file, api_key, args.output, not args.no_preprocessing)
        print(f"翻译结果已保存到: {output_file}")
    except Exception as e:
        print(f"翻译过程中发生错误: {e}")
        exit(1)


if __name__ == "__main__":
    main()
