import subprocess
from typing import Optional


def convert_image(
        input_path: str, output_path: str,
        input_colorspace: str, output_colorspace: str,
        image_size: Optional[tuple[int, int]] = None) -> None:
    command = [
        'oiiotool', '-v', input_path,
        '--colorconvert', input_colorspace, output_colorspace]
    if image_size is not None:
        x, y = image_size
        command.extend(['--resize', f'{x}x{y}'])
    command.extend(['-o', output_path])
    subprocess.run(command)


def convert_image_sequence_to_movie(
        input_path: str | list[str], output_path: str, framerate: int = 24,
        start_number: int = 1, is_stereo: bool = False,
        codec: str = 'mjpeg', quality: int = 2) -> None:
    """Convert image sequence to movie using ffmpeg

    input_path: set frame number with printf syntax padding (%04d, %06d, etc).
    """
    if isinstance(input_path, str):
        input_path = [input_path]
    command = ['ffmpeg']
    for i in input_path:
        command.extend([
            '-framerate', str(framerate),
            '-start_number', str(start_number),
            '-i', i])
    command.extend([
        '-c:v', codec,
        '-q:v', str(quality)])
    if is_stereo:
        command.extend(['-filter_complex', 'hstack,stereo3d=sbsl:arcg'])
    command.extend([output_path, '-y'])
    subprocess.run(command)
