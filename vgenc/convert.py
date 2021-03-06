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
        video_filter: Optional[dict | list[dict]] = None,
        draw_text: Optional[dict | list[dict]] = None,
        metadata: Optional[dict] = None,
        **_) -> None:
    """Convert to movie using ffmpeg

    input_path: set frame number with printf syntax padding (%04d, %06d, etc).
    """

    def build_drawtext(
            fontfile: str,
            fontsize: str,
            fontcolor: str,
            text: str,
            x: int | str,
            y: int | str,
            start_number: Optional[int] = None):
        content = [
            f'fontfile={fontfile}',
            f'text={text}',
            f'fontsize={fontsize}',
            f'fontcolor={fontcolor}',
            f'x={x}',
            f'y={y}']
        if start_number is not None:
            content.extend([f'start_number={start_number}'])
        return f'drawtext={":".join(content)}'

    def build_filter(command: list):
        args = []
        if is_stereo:
            args.append('hstack,stereo3d=sbsl:arcg')
        if resize is not None:
            x, y = resize
            args.append(f'scale={x}:{y}')
        if video_filter is not None:
            # Allow dict for convenience but also list of dict because order
            # can be important
            if isinstance(video_filter, dict):
                filters = [video_filter]
            else:
                filters = video_filter
            for f in filters:
                args.extend([f'{k}={v}' for k, v in f.items()])
        if draw_text is not None:
            # Can draw a single text with dict or multiple one with list of
            # dict
            if isinstance(draw_text, dict):
                texts = [draw_text]
            else:
                texts = draw_text
            for t in texts:
                args.append(build_drawtext(**t))
        if args:
            command.extend(['-filter_complex', ','.join(args)])

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
    build_filter(command)
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
    if metadata is not None:
        command.extend(['-movflags', 'use_metadata_tags'])
        for k, v in metadata.items():
            if v is not None:
                command.extend(['-metadata', f'{k}={v}'])
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


if __name__ == '__main__':
    # Example with text and filter:
    convert_movie(
        input_path='input.mkv',
        output_path='output.mkv',
        draw_text=[
            {'fontfile': 'font.ttf',
             'text': 'frame %{frame_num}',
             'x': 10,
             'y': 10,
             'fontsize': 20,
             'fontcolor': 'white',
             'start_number': 100},
            {'fontfile': 'font.ttf',
             'text': 'description',
             'x': 10,
             'y': 30,
             'fontsize': 20,
             'fontcolor': 'white'}],
        video_filter={
            'scale': '1280x720',
            'pad': 'in_w:in_h+100:0:-50'}
    )
