import subprocess


def extract_frames_from_movie(
        input_path: str, output_path: str, frames: int | list[int]) -> None:
    """Extract frames from movie using ffmpeg

    output_path: set frame number with printf syntax padding (%04d, %06d, etc).
    """
    if isinstance(frames, int):
        frames = [frames]
    command = [
        'ffmpeg', '-i', input_path,
        '-filter:v', 'select=' + '+'.join(
            [rf'eq(n\,{i - 1})' for i in frames]),
        '-frames:v', str(len(frames)),
        '-vsync', 'vfr',
        output_path, '-y']
    subprocess.run(command)
