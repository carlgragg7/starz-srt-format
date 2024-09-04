import subprocess
import re
import logging
import os
import json
# import ffmpeg
import math
from src.services.s3_service import S3Service

class VideoTool:
    def __init__(self):
        self.s3_service = S3Service()

    def extract_audio_from_video(self, video_file, audio_file):
        logging.info(f"Extracting audio {audio_file} from video {video_file}")
        # command = [
        #     "ffmpeg",
        #     "-y",
        #     "-i", video_file,  # Input video file
        #     "-vn",  # Skip video processing
        #     "-acodec", "pcm_s16le",  # WAV format codec
        #     "-ar", "44100",  # Audio sampling rate
        #     "-ac", "2",  # Stereo output
        #     "-threads", "10",  # Use 4 threads for faster processing
        #     audio_file  # Output WAV file path
        # ]
        command = [
            "ffmpeg",
            "-y",
            "-i", video_file,  # Input video file
            "-vn",  # Skip video processing
            "-acodec", "pcm_s16le",  # WAV format codec
            "-ar", "44100",  # Audio sampling rate
            "-ac", "2",  # Stereo output
            "-threads", "10",  # Use 4 threads for faster processing
            "-q:a", "0",
            "-map", "a",
            audio_file  # Output WAV file path
        ]

    #     # Run the command
        subprocess.run(command, check=True)
        logging.info(f"Extracted audio {audio_file} from video {video_file}")
        # subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        # _, stderr = process.communicate()

    #     # if process.returncode != 0:
    #     #     raise Exception(f"FFmpeg error: {stderr.decode()}")

    #     subprocess.run(command, check=True)

    # def extract_audio_from_video(self, video_file, audio_file):
    #     logging.info(f"Extracting audio {audio_file} from video {video_file}")
    #     command = [
    #         "ffmpeg",
    #         "-i", video_file,
    #         "-q:a", "0",
    #         "-map", "a",
    #         audio_file
    #     ]
    #     subprocess.run(command, check=True)
    #     logging.info(f"Extracted audio {audio_file} from video {video_file}")

    def detect_silence(self, input_file):
        logging.info("Detecting silence")
        command = [
            "ffmpeg",
            "-i", input_file,
            "-af", "silencedetect=n=-30dB:d=0.5",
            "-f", "null", "-"
        ]
        result = subprocess.run(command, stderr=subprocess.PIPE, text=True)
        silence_data = result.stderr
        logging.info("Silence detection completed")
        return silence_data

    def parse_silence_data(self, silence_data):
        silence_points = []
        logging.info("Parsing silence data")
        for line in silence_data.split('\n'):
            if "silence_start" in line:
                match = re.search(r'silence_start: (\d+\.\d+)', line)
                if match:
                    start = float(match.group(1))
                    silence_points.append(start)
            elif "silence_end" in line:
                match = re.search(r'silence_end: (\d+\.\d+)', line)
                if match:
                    end = float(match.group(1))
                    silence_points.append(end)
        logging.info(f"Found silence points: {silence_points}")
        return silence_points

    def narrow_silences(self, silence_points, max_duration):
        # TODO: I don't want a 0 second first part and a 0 second last part...
        # TODO: For any split less than a minute, add it to the one before or after
        results = []
        start_index = 0

        while start_index < len(silence_points):
            start_time = silence_points[start_index]
            end_index = start_index

            while end_index < len(silence_points) and (silence_points[end_index] - start_time) < max_duration:
                end_index += 1

            if end_index <= len(silence_points):
                end_index -= 1

            print(f"Start: {start_index}")
            print(f"End: {end_index}")

            # Record the section
            end_time = silence_points[end_index]

            # if start_time == end_time and start_time == 0 and (start_time == silence_points[0] or silence_points[-1]):
            #     start_index = end_index + 1
            #     continue

            results.append(start_time)
            if end_index > start_index:
                results.append(end_time)

            # Move to the next starting point
            start_index = end_index + 1

        return results


    # TODO: We can pip this into memory and stream it directly to open ai instead of saving an entire segment.
    # THIS COULD SPEED THINGS UP
    def process_segment(self, input_file, start_time, end_time, segment_index, base_filename):
        segment_filename = f"{base_filename}_segment_{segment_index:03d}.mp3"
        segment_path = os.path.join('splits/', segment_filename)
        command = [
            "ffmpeg",
            "-i", input_file,
            "-ss", str(start_time),
            "-to", str(end_time),
            "-acodec", "libmp3lame",
            segment_path
        ]
        try:
            result = subprocess.run(command, stderr=subprocess.PIPE, stdout=subprocess.PIPE, text=True, timeout=1000)
            if result.returncode != 0:
                logging.error(f"Error splitting segment {segment_filename}: {result.stderr}")
                return None
            logging.info(f"Created segment: {segment_path}")
            return segment_path
        except subprocess.TimeoutExpired as e:
            logging.error(f"Command timed out: {e}")
            return None
        except subprocess.CalledProcessError as e:
            logging.error(f"Command failed with error: {e.stderr}")
            return None

    def split_audio(self, s3_bucket, input_s3_key, input_file, silence_points, split_duration=1500):
        logging.info(f'Narrowed silence points: {silence_points}')
        print(silence_points)
        segments = []
        prev_end = 0
        segment_index = 0
        base_filename = os.path.basename(input_file).rsplit('.', 1)[0]
        inc_up = 40 / len(silence_points)
        progress_bar = 40

        logging.info("Splitting audio based on silence points")
        for silence_start in silence_points:
            segment_duration = silence_start - prev_end

            if segment_duration <= split_duration:
                # Process the segment as usual
                segment_path = self.process_segment(input_file, prev_end, silence_start, segment_index, base_filename)
                if segment_path:
                    segments.append(segment_path)
                    segment_index += 1
            else:
                # Split the large segment further
                logging.warning(f"Segment from {prev_end} to {silence_start} is larger than split_duration ({split_duration} ms). Splitting further...")
                current_start = prev_end
                while current_start < silence_start:
                    next_split = min(current_start + split_duration, silence_start)
                    segment_path = self.process_segment(input_file, current_start, next_split, segment_index, base_filename)
                    if segment_path:
                        segments.append(segment_path)
                        segment_index += 1
                    current_start = next_split

            prev_end = silence_start
            progress_bar += inc_up
            progress_bar_display = math.ceil(progress_bar)
            self.s3_service.update_status_in_s3(s3_bucket, input_s3_key, 'PROCESSING', progress_bar_display)

        # Handle the final segment after the last silence point
        segment_path = self.process_segment(input_file, prev_end, None, segment_index, base_filename)
        if segment_path:
            segments.append(segment_path)

        # self.s3_service.update_status_in_s3(s3_bucket, input_s3_key, 'PROCESSING', 80)
        return segments


    def compress_audio(self, input_file, output_file):
        command = [
            "ffmpeg",
            "-i", input_file,
            "-vn",
            "-map_metadata", "-1",
            "-ac", "1",
            "-c:a", "libopus",
            "-b:a", "12k",
            "-application", "voip",
            output_file
        ]
        # command = [
        #     "ffmpeg",
        #     "-i", input_file,
        #     "-vn",
        #     "-map_metadata", "-1",
        #     "-ac", "1",
        #     "-c:a", "libopus",
        #     "-b:a", "12k",
        #     "-application", "voip",
        #     "-y",  # Automatically overwrite the output file if it exists
        #     output_file
        # ]

        # Execute the command
        import subprocess

        # with open('/dev/null', 'w') as fnull:
        #     result = subprocess.run(command, check=True, stdout=fnull, stderr=fnull)
        subprocess.run(command, check=True)
        logging.info(f"Compressed {input_file} to {output_file}")


    def verify_file_format(self, file_path, allowed_formats):
        command = [
            "ffprobe", "-v", "error", "-show_entries", "format=format_name",
            "-of", "json", file_path
        ]
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if result.returncode != 0:
            logging.error(f"Error reading file: {result.stderr}")
            return False

        metadata = json.loads(result.stdout)
        format_names = metadata['format']['format_name']
        format_names = format_names.split(',')
        return any(element in allowed_formats for element in format_names)


    def file_size_below_threshold(self, file_path, file_threshold_mb=25):
        file_size_bytes = os.path.getsize(file_path)
        file_size_mb = file_size_bytes / (1024 * 1024)

        print(f'File size mb: {file_size_mb}')
        print(f'File size bytes: {file_size_bytes}')

        if file_size_mb >= file_threshold_mb:
            return False
        else:
            return True
