import openai
import glob
import os
from datetime import datetime, timedelta
import logging

class AiService:
    def __init__(self):
        self.client = openai.OpenAI()

        self.audio_file_path = None
        self.transcription_file_path = None

    # TODO: Transcribe multi languages
    def transcribe(self, audio_file_path, transcription_file_path):
        self.audio_file_path = audio_file_path
        self.transcription_file_path = transcription_file_path

        with open(self.audio_file_path, "rb") as audio_file:
            transcription = self.client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                response_format="srt",
                temperature=0
            )

        # # Save or process the transcription as needed
        # # srt_path = os.path.join('transcriptions/', transcription_file_path)
        with open(transcription_file_path, 'w') as srt_file:
            srt_file.write(transcription)


    def generate_srt(self, transcription_text):
        subtitles = transcription_text.split('.')
        srt_content = ""
        for index, subtitle in enumerate(subtitles, start=1):
            start_time = f"00:00:{index*3:02},000"
            end_time = f"00:00:{index*3 + 2:02},000"
            srt_content += f"{index}\n{start_time} --> {end_time}\n{subtitle.strip()}\n\n"
        return srt_content

    def merge_srt_files_in_directory(self, directory, output_srt_path):
        srt_files = sorted(glob.glob(os.path.join(directory, "*_*.srt")))
        combined_srt_content = ""
        subtitle_index = 1
        cumulative_time = 0  # Cumulative time in milliseconds

        for srt_file in srt_files:
            with open(srt_file, 'r') as file:
                srt_content = file.readlines()

            # Get the last end time in the current combined SRT content
            if subtitle_index > 1:
                last_time_segment = self.extract_last_time_segment(combined_srt_content)
                if last_time_segment:
                    cumulative_time = self.convert_time_to_milliseconds(last_time_segment.split(' --> ')[1])

            for i, line in enumerate(srt_content):
                if line.strip().isdigit():
                    combined_srt_content += f"{subtitle_index}\n"
                    subtitle_index += 1
                elif '-->' in line:
                    start_time, end_time = line.split(' --> ')
                    start_time = self.adjust_time(start_time.strip(), cumulative_time)
                    end_time = self.adjust_time(end_time.strip(), cumulative_time)
                    combined_srt_content += f"{start_time} --> {end_time}\n"
                else:
                    if line.strip() == '' and (i + 1 < len(srt_content) and srt_content[i + 1].strip() == ''):
                        continue
                    combined_srt_content += line

            # Ensure a single blank line is added after each segment block
            if not combined_srt_content.endswith("\n\n"):
                combined_srt_content += "\n"

        with open(output_srt_path, "w") as output_file:
            output_file.write(combined_srt_content)

        return output_srt_path

    def adjust_time(self, original_time, cumulative_time):
        time_format = "%H:%M:%S,%f"
        time_obj = datetime.strptime(original_time, time_format)
        cumulative_time_delta = timedelta(milliseconds=cumulative_time)
        adjusted_time = time_obj + cumulative_time_delta
        return adjusted_time.strftime(time_format)[:-3]  # Truncate microseconds to milliseconds

    def extract_last_time_segment(self, srt_content):
        lines = srt_content.strip().split("\n")
        for line in reversed(lines):
            if '-->' in line:
                return line
        return None

    def convert_time_to_milliseconds(self, time_str):
        time_format = "%H:%M:%S,%f"
        time_obj = datetime.strptime(time_str, time_format)
        return int(time_obj.hour * 3600000 + time_obj.minute * 60000 + time_obj.second * 1000 + time_obj.microsecond / 1000)


    # def adjust_time(self, time_str, offset):
    #     # Convert time_str (in format hh:mm:ss,ms) to seconds, add offset, and convert back
    #     # time_obj = datetime.strptime(time_str.strip(), "%H:%M:%S,%f")
    #     time_obj = datetime.strptime(time_str.strip())
    #     print(time_obj)
    #     adjusted_time = (time_obj - datetime(1900, 1, 1)).total_seconds() + offset
    #     return str(timedelta(seconds=adjusted_time))[:-3].replace('.', ',')

    # def get_last_segment_duration(self, srt_file):
    #     last_start_time = None
    #     last_end_time = None

    #     with open(srt_file, 'r') as file:
    #         for line in file:
    #             if '-->' in line:
    #                 times = line.split(' --> ')
    #                 last_start_time = times[0].strip()
    #                 last_end_time = times[1].strip()

    #     if last_start_time and last_end_time:
    #         start_time_obj = datetime.strptime(last_start_time, "%H:%M:%S,%f")
    #         end_time_obj = datetime.strptime(last_end_time, "%H:%M:%S,%f")
    #         duration = (end_time_obj - start_time_obj).total_seconds()
    #         return duration

    #     logging.error(f"No valid segments found in {srt_file}")
    #     return 0
