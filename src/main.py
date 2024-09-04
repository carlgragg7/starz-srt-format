import os
from concurrent.futures import ThreadPoolExecutor
import multiprocessing as mp
from functools import partial
from multiprocessing import Pool
import concurrent.futures
import numpy as np
import time

import math
from src.utils.thread_safe_counter import ThreadSafeCounter
from src.providers.provider import Provider
from src.services.s3_service import S3Service
from src.utils.video_tool import VideoTool
from src.services.ai_service import AiService

provider = Provider()
video_tool = VideoTool()
s3_service = S3Service()
api_key = s3_service.get_secret().get('OPENAI_API_KEY')
os.environ['OPENAI_API_KEY'] = api_key
ai_service = AiService()
counter = ThreadSafeCounter()

s3_bucket = provider.get_bucket()
input_s3_key = provider.get_input_s3_key()
dest_folder = provider.get_destination_folder()

filename = input_s3_key.split('/')[-1]
provider.create_output_prefix(filename, dest_folder)
log = provider.get_logger(__name__)

def threaded_multiprocess(num_threads, segments):
    log.info("Running %s threads for this process.", num_threads)
    if num_threads > len(segments):
        num_threads = len(segments)

    data_split = np.array_split(segments, num_threads)
    with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = [executor.submit(process_segment, segment_list) for segment_list in data_split]
        for future in concurrent.futures.as_completed(futures):
            try:
                result = future.result()
            except Exception as e:
                log.error(f"Segment processing generated an exception: {e}")

    log.info("Thread complete.")

def parallelize_threads(segments, max_calls_per_sec):
    num_of_processes = mp.cpu_count()

    data_split = np.array_split(segments, num_of_processes)
    print("******* MULTI PROCESS ******")
    print(data_split)
    pool = Pool(num_of_processes)
    num_threads = max_calls_per_sec // num_of_processes

    log.info("Processes (%s) running %s threads", num_of_processes, num_threads)
    pool.map(partial(threaded_multiprocess, num_threads), data_split)

    pool.close()
    pool.join()

def process_segment(segments):
    for segment in segments:
        segment_filename = os.path.basename(segment)
        segment_filename_no_ext = segment_filename.split('.')[0]

        transcript_filename = f"{segment_filename_no_ext}.srt"
        srt_output_path = os.path.join('transcription/', transcript_filename)
        log.info(f"Generating transcript... {srt_output_path}")
        ai_service.transcribe(segment, srt_output_path)

def compress_to_s3(input_s3_key):
    filename = input_s3_key.split('/')[-1]
    input_path = os.path.join('downloads/', filename)
    s3_service.download_file(s3_bucket, input_s3_key, input_path)
    log.info(f"Received file: {input_s3_key}")

    filename_no_ext = filename.rsplit('.', 1)[0]
    new_filename = f'{filename_no_ext}.ogg'
    print(f"\nNew filename: {new_filename}")

    output_s3_key = provider.create_output_key(filename, sub_prefix='compressed_audio', new_file_ext='ogg')
    output_path = os.path.join('compressed/', filename)
    print(f"Output Key: {output_s3_key}")
    print(f"Output Path: {output_path}")

    try:
        log.info("Compressing audio...")
        video_tool.compress_audio(input_path, output_path)
        log.info("File compressed")

        log.info("Uploading file to s3...")
        s3_service.upload_file(output_path, s3_bucket, output_s3_key)
        log.info("File uploaded")
    except Exception as e:
        log.error(f"Error compressing file {input_path}: {str(e)}")
        log.error("Exiting task...")

def process_video_file(input_s3_key):
    log.info("Processing file...")
    s3_service.update_status_in_s3(s3_bucket, input_s3_key, 'PROCESSING', 10)
    filename = input_s3_key.split('/')[-1]
    input_path = os.path.join('downloads/', filename)
    srt_local_path = provider.create_local_path(filename, sub_prefix='transcription', new_file_ext='srt')
    audio_input_path = provider.create_local_path(filename, sub_prefix='downloads', new_file_ext='wav')

    srt_s3_key = provider.create_output_key(filename, 'srt_files', 'srt', add_output_prefix=False)
    # TODO: by streaming this file, it reduces memory needed and makes things much faster
    # TODO: will likely need to migrate to ffmpeg-python library (which could be better long term anyways)
    s3_service.download_file(s3_bucket, input_s3_key, input_path)
    log.info(f"Received file: {input_s3_key}")
    s3_service.update_status_in_s3(s3_bucket, input_s3_key, 'PROCESSING', 20)

    try:
        allowed_formats = ['mp4', 'mov', 'avi', 'wmv', 'avchd', 'webm', 'flv']
        is_valid_format = video_tool.verify_file_format(input_path, allowed_formats)

        if is_valid_format:
            log.info("Verified format, processing...")
            video_tool.extract_audio_from_video(input_path, audio_input_path)
            s3_service.update_status_in_s3(s3_bucket, input_s3_key, 'PROCESSING', 30)

            if video_tool.file_size_below_threshold(audio_input_path, 25):
                log.info("File below 25mb")
                process_segment([audio_input_path])
            else:
                log.info("File above 25mb")
                silence_data = video_tool.detect_silence(audio_input_path)
                silence_points = video_tool.parse_silence_data(silence_data)

                narrowed_silence_points = video_tool.narrow_silences(silence_points, 700)
                s3_service.update_status_in_s3(s3_bucket, input_s3_key, 'PROCESSING', 40)

                segments = video_tool.split_audio(s3_bucket, input_s3_key, audio_input_path, narrowed_silence_points)

                # TODO: Local whisper model can enhance srt accuracy
                # TODO: Language specification can enhance the srt accuracy
                # TODO: The split is bad.
                # TODO: The split skips the beginning of the audio. Possibly more?
                # TODO: The split has less than 1 second segments which cause the api to fail.
                # TODO: Without properly gauging the right timing to 25mb, we're wasting money on the calls to the api.

                s3_service.update_status_in_s3(s3_bucket, input_s3_key, 'PROCESSING', 90)
                parallelize_threads(segments, max_calls_per_sec=5)

                ai_service.merge_srt_files_in_directory('transcription/', srt_local_path)

            s3_service.upload_to_s3_multipart(srt_local_path, s3_bucket, srt_s3_key)
            s3_service.update_status_in_s3(s3_bucket, input_s3_key, 'PROCESSING', 100)

    except Exception as e:
        log.error(f"Error processing file {input_s3_key}: {str(e)}")


def process_audio_file(input_s3_key):
    s3_service.update_status_in_s3(s3_bucket, input_s3_key, 'PROCESSING', 2)
    log.info("Processing file...")
    filename = input_s3_key.split('/')[-1]
    input_path = os.path.join('downloads/', filename)
    srt_local_path = provider.create_local_path(filename, sub_prefix='transcription', new_file_ext='srt')

    srt_s3_key = provider.create_output_key(filename, 'srt_files', 'srt', add_output_prefix=False)
    # TODO: by streaming this file, it reduces memory needed and makes things much faster
    # TODO: will likely need to migrate to ffmpeg-python library (which could be better long term anyways)
    s3_service.download_file(s3_bucket, input_s3_key, input_path)
    log.info(f"Received file: {input_s3_key}")
    s3_service.update_status_in_s3(s3_bucket, input_s3_key, 'PROCESSING', 10)

    try:
        allowed_formats = ['mp3', 'wav']
        is_valid_format = video_tool.verify_file_format(input_path, allowed_formats)

        if is_valid_format:
            log.info("Verified format, processing...")

            if video_tool.file_size_below_threshold(input_path, 25):
                log.info("File below 25mb")
                process_segment([input_path])
            else:
                log.info("File above 25mb")
                silence_data = video_tool.detect_silence(input_path)
                silence_points = video_tool.parse_silence_data(silence_data)

                narrowed_silence_points = video_tool.narrow_silences(silence_points, 700)
                segments = video_tool.split_audio(s3_bucket, input_s3_key, input_path, narrowed_silence_points)

                # TODO: Local whisper model can enhance srt accuracy
                # TODO: Language specification can enhance the srt accuracy
                # TODO: The split is bad.
                # TODO: The split skips the beginning of the audio. Possibly more?
                # TODO: The split has less than 1 second segments which cause the api to fail.
                # TODO: Without properly gauging the right timing to 25mb, we're wasting money on the calls to the api.
                # TODO: Post srt processing, check where there are repeating words and redo that window?
                #   --> Will need to re merge with old srt (Maybe use ai to determine what's wrong with the srt file?)
                parallelize_threads(segments, max_calls_per_sec=5)

                ai_service.merge_srt_files_in_directory('transcription/', srt_local_path)

            s3_service.upload_to_s3_multipart(srt_local_path, s3_bucket, srt_s3_key)

    except Exception as e:
        log.error(f"Error processing file {input_s3_key}: {str(e)}")


if __name__ == '__main__':
    log.info("Running application")
    process_video_file(input_s3_key)
    s3_service.update_status_in_s3(s3_bucket, input_s3_key, 'FINISHED', 100)
