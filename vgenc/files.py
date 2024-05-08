import os
import re
from subprocess import run
from typing import Literal
from .probe import get_image_size

MissingFramesLiteral = Literal['previous', 'black', 'checkerboard']


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


def generate_missing_frames(
        input_path: str,
        frame_range: tuple[int, int],
        start_number: int,
        missing_frames: MissingFramesLiteral
        ) -> list:

    def replace_frame_padding(name: str, frame: int, padding: int) -> str:
        return name.replace(f'%0{padding}d', str(frame).zfill(padding))

    matched = re.match(r'.*?%(.*)d', input_path)
    if matched is None:
        return
    padding = int(matched.group(1))
    missing_files = []
    for frame in reversed(range(frame_range[0], frame_range[1] + 1)):
        # Start from last frame to make sure previous mode find real
        # file and not symlink
        target_filepath = replace_frame_padding(
            input_path, frame, padding)
        if os.path.exists(target_filepath):
            continue
        match missing_frames:
            case 'previous':
                for f in reversed(range(start_number, frame)):
                    looked_file = replace_frame_padding(input_path, f, padding)
                    if os.path.exists(looked_file):
                        looked_file = os.path.basename(looked_file)
                        os.symlink(looked_file, target_filepath)
                        break
            case 'black' | 'checkerboard' as c:
                # Assume first frame exists and has correct resolution
                get_first_file = replace_frame_padding(
                    input_path, start_number, padding)
                x, y = get_image_size(get_first_file)
                bg_args = {
                    'black': 'canvas:black',
                    'checkerboard': 'pattern:checkerboard'}
                run([
                    'magick',
                    '-size',
                    f'{x}x{y}',
                    bg_args[c],
                    target_filepath])
        missing_files.append(target_filepath)
    return missing_files
