import os
import subprocess
from typing import Optional

ffmpeg_video_codecs = {
    'copy': 'copy',
    'vp9': 'libvpx-vp9',
    'av1': 'libaom-av1',
    'theora': 'libtheora',
    'mjpeg': 'mjpeg',
    'h264': 'libx264',
    'h265': 'libx265'}
ffmpeg_audio_codecs = {
    'copy': 'copy',
    'flac': 'flac',
    'opus': 'libopus',
    'vorbis': 'libvorbis',
    'mp3': 'libmp3lame'}


def convert_image(
        input_path: str,
        output_path: str,
        colorspace: Optional[tuple[str, str]] = None,
        look: Optional[str] = None,
        image_size: Optional[tuple[int, int]] = None,
        compression: Optional[str] = None,
        **_) -> None:
    """Convert image using oiiotool"""
    command = ['oiiotool', '-v', input_path]
    if colorspace is not None:
        command.append('--colorconvert')
        command.extend(colorspace)
    if look is not None:
        command.extend(['--ociolook', look])
    if image_size is not None:
        x, y = image_size
        command.extend(['--resize', f'{x}x{y}'])
    if compression is not None:
        command.extend(['--compression', compression])
    command.extend(['-o', output_path])
    subprocess.run(command)


def convert_movie(
        input_path: str | list[str],
        output_path: str,
        framerate: Optional[int] = None,
        start_number: Optional[int] = None,
        video_codec: Optional[str] = None,
        video_quality: Optional[int] = None,
        video_bitrate: Optional[str] = None,
        constrained_quality: Optional[int] = None,
        audio_codec: Optional[str] = None,
        audio_quality: Optional[int] = None,
        audio_bitrate: Optional[str] = None,
        resize: Optional[tuple[int, int]] = None,
        is_stereo: bool = False,
        two_pass: bool = False,
        **_) -> None:
    """Convert to movie using ffmpeg

    input_path: set frame number with printf syntax padding (%04d, %06d, etc).
    """
    if isinstance(input_path, str):
        input_path = [input_path]
    command = ['ffmpeg']
    for i in input_path:
        if framerate is not None:
            command.extend(['-framerate', str(framerate)])
        if start_number is not None:
            command.extend(['-start_number', str(start_number)])
        command.extend(['-i', i])
    if video_codec is not None:
        vc = ffmpeg_video_codecs.get(video_codec, video_codec)
        command.extend(['-c:v', vc])
    if video_quality is not None:
        command.extend(['-q:v', str(video_quality)])
    if constrained_quality is not None:
        command.extend(['-crf', str(constrained_quality)])
    if video_bitrate is not None:
        # to enable constant quality instead of constrained quality, bitrate
        # should be set to 0.
        command.extend(['-b:v', str(video_bitrate)])
    if resize is not None:
        x, y = resize
        command.extend(['-vf', f'{x}:{y}'])
    if is_stereo:
        command.extend(['-filter_complex', 'hstack,stereo3d=sbsl:arcg'])
    if two_pass:
        first_pass_command = command.copy()
        first_pass_command.extend([
            '-pass', '1', '-an', '-f', 'null',
            'NUL' if os.name == 'nt' else '/dev/null'])
        subprocess.run(first_pass_command)
        command.extend(['-pass', '2'])
    if audio_codec is not None:
        ac = ffmpeg_audio_codecs.get(audio_codec, audio_codec)
        command.extend(['-c:a', ac])
    if audio_quality is not None:
        command.extend(['-q:a', str(audio_quality)])
    if audio_bitrate is not None:
        command.extend(['-b:a', str(audio_bitrate)])
    command.extend([output_path, '-y'])
    subprocess.run(command)


def convert_to_gif(
        input_path: str | list[str],
        output_path: str,
        fps: int = 15,
        optimize: bool = True,
        depth: int = 8,
        bounce: bool = False):
    """Convert images to gif

    input_path can be folder or list of image paths."""

    if isinstance(input_path, str):
        if os.path.isdir(input_path):
            input_path = [
                os.path.join(input_path, i) for i in os.listdir(input_path)]
            input_path.sort()

    fps = '1x{}'.format(fps)
    command = [
        'magick',
        '-delay', fps,
        '-loop', '0']
    command.extend(input_path)
    if bounce:
        command.extend(['-duplicate', '1,-2-1'])
    if optimize:
        command.extend(['-layers', 'optimize'])
    if depth:
        command.extend(['-depth', str(depth)])
    if not output_path.endswith('.gif'):
        output_path += '.gif'
    command.append(output_path)
    subprocess.run(command)
