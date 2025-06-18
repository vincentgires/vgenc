import os
import re
from pathlib import Path
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
        suffix: str = '',
        filter_files: bool = False) -> tuple[int, int]:
    dirname = os.path.dirname(path)
    files = sorted(os.listdir(dirname))
    if filter_files:
        files = [f for f in files if os.path.isfile(os.path.join(dirname, f))]
    search_pattern = rf'{prefix}(\d{{{digits}}}){suffix}'
    files_ = files[0], files[-1]
    frames = [
        int(m.group(1)) for m in [re.search(search_pattern, f) for f in files_]
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


def find_frame_mapping_from_hash_pattern(
        path: str | Path) -> tuple[str, dict[int, Path]]:
    path = Path(path)
    dirname = path.parent
    basename = path.name

    # Match hash pattern (e.g. ####) to find:
    # - prefix
    # - suffix
    # - number of digits
    m = re.match(r'(.*?)(#+)(\..*)', basename)
    if not m:
        return

    prefix, hashes, suffix = m.groups()
    digits = len(hashes)

    frame_pattern = re.compile(
        rf'^{re.escape(prefix)}(\d{{{digits}}}){re.escape(suffix)}$')
    frame_map = {}

    for file in sorted(dirname.iterdir()):
        if file.is_file():
            match = frame_pattern.match(file.name)
            if match:
                frame_num = int(match.group(1))
                frame_map[frame_num] = file.name

    return dirname, frame_map


def fill_missing_images(
        frame_mapping: dict[int, str], start: int, end: int) -> list[str]:
    """
    Return a list of images for frames in range(start, end),
    filling missing frames with the nearest available frame's filename.
    """
    available_frames = sorted(frame_mapping.keys())
    filled = []
    for i in range(start, end + 1):
        if i in frame_mapping:
            filled.append(frame_mapping[i])
        else:
            nearest = min(available_frames, key=lambda x: abs(x - i))
            filled.append(frame_mapping[nearest])
    return filled


if __name__ == '__main__':
    path = '/path/file.####.png'
    directory, frame_mapping = find_frame_mapping_from_hash_pattern(path)
    images = fill_missing_images(frame_mapping, *(101, 200))
