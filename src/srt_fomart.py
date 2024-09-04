import json
import textwrap

# formating rules
# - 3 to 7 seconds on screen
# - Don't split lines

def get_items_in_segment(items, segment):
    return_items = []
    for item_index in segment["items"]:
        return_items.append(items[item_index])
    return return_items


def combine_segment_items(items_in_segment):
    current_text = ""

    for item in items_in_segment:
        if item["type"] == "pronunciation":
            word = item["alternatives"][0]["content"]
            current_text += word + " "

        elif item["type"] == "punctuation":
            punctuation = item["alternatives"][0]["content"]
            current_text = current_text.strip() + punctuation + " "

    return current_text


def split_segment(items_in_segment, char_limit, srt_counter):
    current_text = ""
    start_time = ""
    end_time = ""
    lines = []

    for index, item in enumerate(items_in_segment):
        if item["type"] == "pronunciation":
            word = item["alternatives"][0]["content"]
            if not start_time:
                start_time = item["start_time"]
            end_time = item["end_time"]
            current_text += word + " "

        elif item["type"] == "punctuation":
            punctuation = item["alternatives"][0]["content"]
            current_text = current_text.strip() + punctuation + " "

        is_last_item = index == len(items_in_segment) - 1
        is_next_not_punctuation = (
            not is_last_item and not items_in_segment[index + 1]["type"] == "punctuation"
        )

        if (
            len(current_text.strip()) >= char_limit
            and is_next_not_punctuation
            or is_last_item
        ):
            if start_time and end_time:
                lines.append(f"{srt_counter}\n")
                lines.append(
                    f"{format_time(start_time)} --> {format_time(end_time)}\n"
                )
                lines.append(f"{current_text}\n\n")
                srt_counter += 1
            current_text = ""
            start_time = ""

    return lines, srt_counter


def json_to_srt(json_file, output_srt_file, char_limit=42):
    with open(json_file, "r") as f:
        data = json.load(f)

    items = data["results"]["items"]
    segments = data["results"]["audio_segments"]

    srt_counter = 1
    current_text = ""
    start_time = ""
    end_time = ""

    with open(output_srt_file, "w") as srt:
        for segment in segments:
            items_in_segment = get_items_in_segment(items, segment)
            current_text = segment['transcript']

            if len(current_text.strip()) <= char_limit:
                start_time = segment["start_time"]
                end_time = segment["end_time"]

                if start_time and end_time:
                    wrapped_lines = textwrap.wrap(
                        current_text.strip(), width=char_limit
                    )
                    for line in wrapped_lines:
                        srt.write(f"{srt_counter}\n")
                        srt.write(
                            f"{format_time(start_time)} --> {format_time(end_time)}\n"
                        )
                        srt.write(f"{line}\n\n")
                        srt_counter += 1
            else:
                split_lines, srt_counter = split_segment(items_in_segment, char_limit, srt_counter)
                for line in split_lines:
                    srt.write(line)

            current_text = ""
            start_time = ""


def format_time(time_in_seconds):
    if not time_in_seconds:
        return "00:00:00,000"

    hours, remainder = divmod(float(time_in_seconds), 3600)
    minutes, seconds = divmod(remainder, 60)
    milliseconds = (seconds % 1) * 1000
    return f"{int(hours):02}:{int(minutes):02}:{int(seconds):02},{int(milliseconds):03}"


json_to_srt("El_Jeremias_Spanish_feature_2398.json", "output2.srt", char_limit=42)
