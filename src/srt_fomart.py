import json
import textwrap

def json_to_srt(json_file, output_srt_file, char_limit=42):
    # Load the JSON data
    with open(json_file, 'r') as f:
        data = json.load(f)
    
    items = data['results']['items']
    srt_counter = 1
    current_text = ""
    start_time = ""
    end_time = ""
    
    with open(output_srt_file, 'w') as srt:
        for index, item in enumerate(items):
            if item['type'] == 'pronunciation':
                word = item['alternatives'][0]['content']
                if not start_time:
                    start_time = item['start_time']
                end_time = item['end_time']
                current_text += word + " "
            
            elif item['type'] == 'punctuation':
                punctuation = item['alternatives'][0]['content']
                current_text = current_text.strip() + punctuation + " "
                
            # Check if the next item is the end of a sentence or the end of the list
            is_last_item = index == len(items) - 1
            is_next_punctuation = not is_last_item and items[index + 1]['type'] == 'punctuation'
            
            # If the current text is longer than the char limit or we encounter punctuation, write the SRT segment
            if len(current_text.strip()) >= char_limit and is_next_punctuation or is_last_item:
                # Ensure start and end times are set
                if start_time and end_time:
                    # Split into lines with the char limit
                    wrapped_lines = textwrap.wrap(current_text.strip(), width=char_limit)
                    for line in wrapped_lines:
                        srt.write(f"{srt_counter}\n")
                        srt.write(f"{format_time(start_time)} --> {format_time(end_time)}\n")
                        srt.write(f"{line}\n\n")
                        srt_counter += 1
                current_text = ""
                start_time = ""
                
def format_time(time_in_seconds):
    # Ensure the time_in_seconds is not empty or None
    if not time_in_seconds:
        return "00:00:00,000"
    
    hours, remainder = divmod(float(time_in_seconds), 3600)
    minutes, seconds = divmod(remainder, 60)
    milliseconds = (seconds % 1) * 1000
    return f"{int(hours):02}:{int(minutes):02}:{int(seconds):02},{int(milliseconds):03}"

# Example usage
json_to_srt('El_Jeremias_Spanish_feature_2398.json', 'output2.srt', char_limit=42)
