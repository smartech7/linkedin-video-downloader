from itertools import starmap
import re


def subtitles_time_format(ms):
    """
    Formats subtitles time
    """
    seconds, milliseconds = divmod(ms, 1000)
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    return f'{hours:02}:{minutes:02}:{seconds:02},{milliseconds:02}'


def write_subtitles(count, subs, video_name, video_duration):
    """
    Writes to a file(subtitle file) caption matching the right time
    """
    def subs_to_lines(idx, sub):
        starts_at = sub['transcriptStartAt']
        ends_at = subs[idx]['transcriptStartAt'] if idx < len(
            subs) else video_duration
        caption = sub['caption']
        return f"{idx}\n" \
            f"{subtitles_time_format(starts_at)} --> {subtitles_time_format(ends_at)}\n" \
            f"{caption}\n\n"

    with open(f"{count}-{video_name.strip()}.srt", 'wb') as f:
        for line in starmap(subs_to_lines, enumerate(subs, start=1)):
            f.write(line.encode('utf8'))
