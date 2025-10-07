import os
import argparse
import subprocess
from modelscope.pipelines import pipeline
from modelscope.utils.constant import Tasks
from gpu_utils import detect_gpu_support, get_ffmpeg_video_to_audio_args, print_gpu_info


def reduce_noise(input_path, output_path=None, use_gpu=True):
    """
    Apply noise reduction to an audio or video file using the speech_zipenhancer model.
    Supports GPU acceleration for video-to-audio conversion.

    Args:
        input_path (str): Path to the input audio or video file
        output_path (str, optional): Path to save the denoised audio file.
                                   If None, will use a default name.
        use_gpu (bool): Whether to use GPU acceleration for video conversion

    Returns:
        str: Path to the denoised audio file, or the input path if reduction failed
    """
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Input file not found: {input_path}")

    # Generate output path if not provided
    if output_path is None:
        input_name = os.path.splitext(os.path.basename(input_path))[0]
        # Create data directory structure: data/[original_filename]/denoised.wav
        data_dir = "data"
        output_dir = os.path.join(data_dir, input_name)
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, "denoised.wav")

    # Check if input is a video file and convert to audio if needed
    input_ext = os.path.splitext(input_path)[1].lower()
    video_extensions = ['.mp4', '.avi', '.mov', '.mkv', '.webm', '.flv', '.wmv', '.m4v']

    if input_ext in video_extensions:
        print(f"Input is a video file ({input_ext}), converting to audio...")

        # Detect GPU support if GPU is enabled
        gpu_type = 'none'
        if use_gpu:
            gpu_info = detect_gpu_support()
            gpu_type = gpu_info['gpu_type']
            print(f"GPU acceleration: {gpu_info['details']}")
        else:
            print("GPU acceleration disabled, using CPU")

        # Generate path for the converted audio file
        input_name = os.path.splitext(os.path.basename(input_path))[0]
        data_dir = "data"
        output_dir = os.path.join(data_dir, input_name)
        os.makedirs(output_dir, exist_ok=True)
        audio_file_path = os.path.join(output_dir, "original_audio.wav")

        # Copy original video to output directory
        original_video_path = os.path.join(output_dir, os.path.basename(input_path))
        print(f"Copying original video: {input_path} -> {original_video_path}")
        try:
            subprocess.run(['cp', input_path, original_video_path], check=True)
            print(f"Original video copied successfully!")
        except subprocess.CalledProcessError as e:
            print(f"Failed to copy original video: {e}")
            # Continue with processing even if copy fails

        print(f"Converting video to audio: {input_path} -> {audio_file_path}")
        try:
            # Use shared GPU utility for video-to-audio conversion
            cmd_args = get_ffmpeg_video_to_audio_args(input_path, audio_file_path, gpu_type)
            subprocess.run(cmd_args, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            print(f"Video to audio conversion completed successfully! ({gpu_info['details'] if use_gpu else 'CPU'})")
            input_path = audio_file_path  # Use the converted audio for noise reduction
        except subprocess.CalledProcessError as e:
            print(f"Video to audio conversion failed: {e}")
            raise Exception(f"Failed to convert video to audio: {e}")
    else:
        print(f"Input is an audio file, proceeding with noise reduction...")

        # Copy original audio to output directory
        if output_path is None:  # Only copy for default output path
            input_name = os.path.splitext(os.path.basename(input_path))[0]
            data_dir = "data"
            output_dir = os.path.join(data_dir, input_name)
            os.makedirs(output_dir, exist_ok=True)
            original_audio_path = os.path.join(output_dir, os.path.basename(input_path))

            print(f"Copying original audio: {input_path} -> {original_audio_path}")
            try:
                subprocess.run(['cp', input_path, original_audio_path], check=True)
                print(f"Original audio copied successfully!")
            except subprocess.CalledProcessError as e:
                print(f"Failed to copy original audio: {e}")
                # Continue with processing even if copy fails

    print("Applying noise reduction...")

    try:
        # Initialize the noise suppression model
        enhance_video = pipeline(
            Tasks.acoustic_noise_suppression,
            model='iic/speech_zipenhancer_ans_multiloss_16k_base'
        )

        # Apply noise reduction
        result = enhance_video(input_path, output_path=output_path)

        # Determine the actual output file path
        if hasattr(result, 'output_path') and result.output_path:
            actual_output_path = result.output_path
        elif isinstance(result, str) and result:
            actual_output_path = result
        elif os.path.exists(output_path):
            actual_output_path = output_path
        else:
            print("Noise reduction may not have completed successfully")
            return input_path

        print(f"Noise reduction completed. Output saved to: {actual_output_path}")
        return actual_output_path

    except Exception as e:
        print(f"Noise reduction failed: {e}")
        print("Using original audio without noise reduction")
        return input_path

    finally:
        # Clean up the model to free memory
        if 'enhance_video' in locals():
            del enhance_video


def main():
    """
    Command-line interface for noise reduction.
    """
    parser = argparse.ArgumentParser(
        description='Apply noise reduction to audio or video files using speech_zipenhancer model',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  python noise_reduction.py input.mp4                    # 默认GPU加速
  python noise_reduction.py input.mp4 --no-gpu          # 禁用GPU加速
  python noise_reduction.py input.mp4 -o output.wav
  python noise_reduction.py input.wav --gpu-info        # 显示GPU信息
        """
    )
    parser.add_argument('input', nargs='?', help='Path to the input audio or video file')
    parser.add_argument('-o', '--output', help='Path to save the denoised audio file')
    parser.add_argument('--no-gpu', action='store_true', help='Disable GPU acceleration for video conversion')
    parser.add_argument('--gpu-info', action='store_true', help='Show GPU acceleration information and exit')

    args = parser.parse_args()

    # Show GPU info and exit if requested
    if args.gpu_info:
        print_gpu_info()
        return

    # Check if input file is provided
    if not args.input:
        print("Error: input file is required")
        parser.print_help()
        exit(1)

    try:
        use_gpu = not args.no_gpu
        output_path = reduce_noise(args.input, args.output, use_gpu=use_gpu)
        if output_path != args.input:
            print(f"Successfully processed: {args.input} -> {output_path}")
        else:
            print("Noise reduction failed, using original file")

    except FileNotFoundError as e:
        print(f"Error: {e}")
        exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}")
        exit(1)


if __name__ == "__main__":
    main()