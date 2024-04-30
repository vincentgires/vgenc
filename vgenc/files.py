import os
import re


def get_frame_info(path: str) -> dict:
    # "#" successive number
    if pattern := re.search(r'#+', path):
        # Detect /path/filename.####.exr
        num_digits = len(pattern.group(0))
        number = None
    # Padding format: %04d, %06d, etc
    elif pattern := re.search(r'%(\d+)d', path):
        # Detect /path/filename.%04d.exr
        num_digits = int(pattern.group(1))
        number = None
    # Raw number
    elif pattern := re.search(r'\d+(?=[^\d]*$)', path):
        # Detect /path/filename.1234.jpg
        num_digits = len(pattern.group())
        number = int(pattern.group())
    else:
        return
    return {
        'digits': num_digits,
        'start': path[:pattern.start()],  # 'filename.'
        'end': path[pattern.end():],  # '.exr'
        'number': number}


def find_image_sequence_range(
        path: str,
        digits: int,
        prefix: str = '',
        suffix: str = ''
        ) -> tuple[int, int]:
    dirname, basename = os.path.split(path)
    files = sorted(os.listdir(dirname))
    files = [
        os.path.join(dirname, f) for f in files
        if os.path.isfile(os.path.join(dirname, f))]
    search_pattern = rf'{prefix}(\d{{{digits}}}){suffix}'
    frames = [
        int(m.group(1)) for m in [re.search(search_pattern, f) for f in files]
        if m is not None]
    if frames:
        return (frames[0], frames[-1])
