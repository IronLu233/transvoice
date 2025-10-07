from faster_whisper import WhisperModel
from silero_vad import load_silero_vad, read_audio, get_speech_timestamps
import json
import os
import sys
import argparse
from pydub import AudioSegment


def get_default_output_path(input_file_path, file_type='asr'):
    """
    Get default output path based on input file type.

    Args:
        input_file_path (str): Path to the input file
        file_type (str): Type of file ('asr' or 'segments')

    Returns:
        str: Default output path
    """
    input_ext = os.path.splitext(input_file_path)[1].lower()
    video_extensions = ['.mp4', '.avi', '.mov', '.mkv', '.webm', '.flv', '.wmv', '.m4v']

    if input_ext in video_extensions:
        # For video files, save in data/[video_name]/ directory
        video_name = os.path.splitext(os.path.basename(input_file_path))[0]
        data_dir = "data"
        output_dir = os.path.join(data_dir, video_name)
        os.makedirs(output_dir, exist_ok=True)

        if file_type == 'asr':
            return os.path.join(output_dir, 'asr_results.json')
        elif file_type == 'segments':
            return os.path.join(output_dir, 'audio_segments')
    else:
        # For audio files, save in the same directory as input
        input_dir = os.path.dirname(input_file_path)
        input_name = os.path.splitext(os.path.basename(input_file_path))[0]

        if file_type == 'asr':
            return os.path.join(input_dir, f'{input_name}_asr_results.json')
        elif file_type == 'segments':
            return os.path.join(input_dir, f'{input_name}_audio_segments')


def perform_asr(audio_file_path):
    """
    Perform Automatic Speech Recognition on an audio file.

    Args:
        audio_file_path (str): Path to the input audio file

    Returns:
        dict: ASR results with segments information
        str: Path to the audio file used for ASR
    """

    # Step 1: VAD
    print("Step 1: Performing Voice Activity Detection...")
    vad_model = load_silero_vad()

    speech_timestamps = get_speech_timestamps(
        read_audio(audio_file_path),
        vad_model,
        min_silence_duration_ms=2000,
        return_seconds=True,
    )
    print(f"Found {len(speech_timestamps)} speech segments")

    # Step 2: ASR
    print("Step 2: Performing Automatic Speech Recognition...")
    model_size = "large"
    asr_model = WhisperModel(model_size, device="auto", compute_type="float16")

    initial_prompt = '''
This is an educational video about ICT (Inner Circle Trader) trading strategy and concepts in English.
Please pay special attention to the following trading terminology and transcribe them accurately:

Core ICT Trading Terms:
- AMD (Accumulation, Manipulation, Distribution), PO3 (Power of Three)
- BISI (Buy Side Imbalance Sell Side Inefficiency), SIBI (Sell Side Imbalance Buy Side Inefficiency)
- BPR (Balanced Price Range), BSL (Buy Side Liquidity), SSL (Sell Side Liquidity)
- BE (Breakeven), BOS (Break of Structure), CE (Consequent Encroachment)
- FVG (Fair Value Gap), IFVG (Inversion Fair Value Gap)
- HTF (Higher Time Frame), LTF (Lower Time Frame), IPDA (Inter Bank Price Delivery Algorithm)
- STH (Short Term High), ITH (Intermediate Term High), LTH (Long Term High)
- STL (Short Term Low), ITL (Intermediate Term Low), LTL (Long Term Low)
- MSS (Market Structure Shift), MT (Mean Threshold), OB (Order Block)
- OTE (Optimal Trade Entry), PDL (Previous Day Low), PDH (Previous Day High)
- ERL (External Range Liquidity), IRL (Internal Range Liquidity), PD Array (Premium & Discount Array)
- BB (Breaker Block), MB (Mitigation Block), NWOG (New Week Opening Gap)
- LP (Liquidity Pool), TGIF (Thanks God It's Friday)

Traditional Trading Terms:
- Silver Bullet, Lot, Spread, Margin, Leverage, Bid, Ask, Swap
- Forex, Long, Short, Stop Loss, Take Profit, pip, pips, handle, handles, tick, ticks, point, points
- Draw on liquidity, liquidity pools, bear order block, bull order block, equal low (EQL), equal high (EQH)
- session, liquidity, probability, smart money, liquidity raid, stop hunt
- retail, institutional, price, up close candle

Key Concepts:
- ICT methodology, market structure, price action, smart money concepts
- Supply and demand zones, market makers, liquidity analysis, order flow
- Trading psychology, risk management, trade execution
- Premium and discount, price delivery algorithm, market structure shifts

Please ensure accurate transcription of these specific ICT terms and concepts as they are crucial for the educational content.
    '''

    # Convert speech_timestamps to clip_timestamps format
    clip_timestamps = []
    for timestamp in speech_timestamps:
        clip_timestamps.extend([timestamp["start"], timestamp["end"]])

    segments, _ = asr_model.transcribe(audio_file_path, beam_size=5, language="en",
                                       multilingual=False,
                                     initial_prompt=initial_prompt, clip_timestamps=clip_timestamps)

    asr_segments = []


    for i, segment in enumerate(segments):
        current_segment = {
            'start': round(segment.start * 1000),
            'end': round(segment.end * 1000),
            'text': segment.text.strip()
        }

        # Check if we should merge with previous segment
        if i > 0 and asr_segments:
            previous_segment = asr_segments[-1]
            gap = current_segment['start'] - previous_segment['end']

            # If gap is less than 5ms, merge current segment into previous one
            if gap < 5:
                previous_segment['end'] = current_segment['end']
                previous_segment['text'] += ' ' + current_segment['text']
                print(f"segment {i}: Merged with previous segment (gap: {gap}ms)")
            else:
                asr_segments.append(current_segment)
                print(f"segment {i}: {segment.text}")
        else:
            asr_segments.append(current_segment)
            print(f"segment {i}: {segment.text}")

    # Prepare ASR results
    asr_results = {
        'total_segments': len(asr_segments),
        'segments': asr_segments
    }

    return asr_results, audio_file_path

def extract_audio_segments(media_file_path, asr_results_path, output_dir='audio_segments'):
    """
    Extract audio segments based on ASR results.

    Args:
        media_file_path (str): Path to the input video or audio file
        asr_results_path (str): Path to the ASR results JSON file
        output_dir (str): Directory to save the extracted audio segments (default: 'audio_segments')

    Returns:
        bool: True if extraction was successful, False otherwise
    """
    print("Step 4: Extracting audio segments...")

    # Load ASR results
    try:
        with open(asr_results_path, 'r', encoding='utf-8') as f:
            asr_data = json.load(f)
        segments = asr_data['segments']
        print(f"Loaded {len(segments)} segments from {asr_results_path}")
    except Exception as e:
        print(f"Failed to load ASR results: {e}")
        return False

    # Create output directory
    os.makedirs(output_dir, exist_ok=True)
    print(f"Output directory: {output_dir}")

    # Load audio/video file
    try:
        audio = AudioSegment.from_file(media_file_path)
        print(f"Loaded media file: {media_file_path}")
    except Exception as e:
        print(f"Failed to load media file: {e}")
        return False

    total_segments = len(segments)
    success_count = 0
    error_count = 0

    print(f"Processing {total_segments} audio segments...")

    # Extract each segment
    for i, segment in enumerate(segments):
        segment_index = i + 1
        try:
            # Time is already in milliseconds
            start_ms = int(segment['start'])
            end_ms = int(segment['end'])

            # Extract segment
            audio_segment = audio[start_ms:end_ms]

            # Create output filename
            output_filename = f"segment_{segment_index:03d}_{start_ms}-{end_ms}.wav"
            output_path = os.path.join(output_dir, output_filename)

            # Export segment
            audio_segment.export(output_path, format="wav", parameters=["-ar", "16000", "-ac", "1"])

            success_count += 1
            print(f"✓ Segment {segment_index:03d}: {start_ms}-{end_ms}ms -> {output_filename}")

        except Exception as e:
            error_count += 1
            print(f"✗ Segment {segment_index:03d}: {segment['start']}-{segment['end']}ms -> ERROR: {str(e)}")

    print(f"\nExtraction complete: {success_count} successful, {error_count} failed")

    if error_count > 0:
        print(f"Warning: {error_count} segments failed to extract")

    return error_count == 0


def main():
    """
    Main function for command-line execution.
    """
    parser = argparse.ArgumentParser(description='Perform ASR and audio segmentation on audio or video files')
    parser.add_argument('input_file', help='Path to the input audio or video file')
    parser.add_argument('--asr-output',
                       help='Path to save ASR results (default: determined by input file type)')
    parser.add_argument('--segments-dir',
                       help='Directory to save audio segments (default: determined by input file type)')
    parser.add_argument('--skip-segments', action='store_true',
                       help='Skip audio segment extraction, only perform ASR')

    args = parser.parse_args()

    # Set default output paths if not provided
    asr_output = args.asr_output if args.asr_output else get_default_output_path(args.input_file, 'asr')
    segments_dir = args.segments_dir if args.segments_dir else get_default_output_path(args.input_file, 'segments')

    try:
        # Perform ASR
        print(f"Processing input file: {args.input_file}")
        asr_results, audio_file = perform_asr(args.input_file)

        # Save ASR results
        with open(asr_output, 'w', encoding='utf-8') as f:
            json.dump(asr_results, f, ensure_ascii=False, indent=2)
        print(f"ASR results saved to {asr_output}")

        # Extract audio segments unless skipped
        if not args.skip_segments:
            success = extract_audio_segments(args.input_file, asr_output, segments_dir)
            if success:
                print(f"Audio extraction complete. {asr_results['total_segments']} segments saved to '{segments_dir}' directory.")
            else:
                print("Audio extraction completed with some errors.")
        else:
            print("Audio segment extraction skipped as requested.")

        print("Processing completed successfully!")

    except Exception as e:
        print(f"Error during processing: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
