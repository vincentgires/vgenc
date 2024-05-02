import os
import re
import tempfile
import shutil
import subprocess
from typing import Optional, Literal
from .probe import get_image_size
from .files import get_frame_info

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

temporary_ext = '.jpg'
temporary_compression = 'jpeg:95'

MissingFramesLiteral = Literal['previous', 'black', 'checkerboard']


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
                subprocess.run([
                    'magick',
                    '-size',
                    f'{x}x{y}',
                    bg_args[c],
                    target_filepath])
        missing_files.append(target_filepath)
    return missing_files


def convert_image(
        input_path: str,
        output_path: str,
        input_colorspace: Optional[str] = None,
        color_convert: Optional[tuple[str, str]] = None,
        look: Optional[str] = None,
        display_view: Optional[tuple[str, str]] = None,
        image_size: Optional[tuple[int, int]] = None,
        compression: Optional[str] = None,
        rgb_only: bool = False,
        data_format: Optional[str | list] = None,
        # Image sequence arguments
        image_sequence: bool = False,
        frame_range: tuple[int, int] = (1, 1),
        frame_jump: int = 1,
        **_) -> None:
    """Convert image using oiiotool

    input_colorspace: needed for display_view.
    """

    if image_sequence:
        def build_path(path: str) -> str:
            frame_info = get_frame_info(path)
            frame_path = (
                f"{frame_info['start']}"
                f"{frame:0{frame_info['digits']}d}"
                f"{frame_info['end']}")
            return frame_path

        frame_start, frame_end = frame_range
        for frame in range(frame_start, frame_end + 1, frame_jump):
            convert_image(
                input_path=build_path(input_path),
                output_path=build_path(output_path),
                input_colorspace=input_colorspace,
                color_convert=color_convert,
                look=look,
                display_view=display_view,
                image_size=image_size,
                compression=compression,
                rgb_only=rgb_only,
                data_format=data_format)
        return

    command = ['oiiotool', '-v']
    if rgb_only:
        command.append(['-i:ch=R,G,B'])
    command.append(input_path)
    if input_colorspace is not None:
        command.extend(['--iscolorspace', input_colorspace])
    if color_convert is not None:
        command.append('--colorconvert')
        command.extend(color_convert)
    if look is not None:
        command.extend(['--ociolook', look])
    if display_view is not None:
        command.append('--ociodisplay')
        command.extend(display_view)
    if image_size is not None:
        x, y = image_size
        command.extend(['--resize', f'{x}x{y}'])
    if compression is not None:
        command.extend(['--compression', compression])
    if data_format is not None:
        # Can set a single data format or a list to specify channel formats
        # -d half -d Z=float
        df = [data_format] if isinstance(data_format, str) else data_format
        for d in df:
            command.extend(['-d', d])
    command.extend(['-o', output_path])
    subprocess.run(command)


def _replace_ext(file_path: str, ext: str) -> str:
    path, old_ext = os.path.splitext(file_path)
    return path + ext


def convert_movie(
        input_path: str | list[str],
        output_path: str,
        frame_rate: Optional[int] = None,
        start_number: Optional[int] = None,
        missing_frames: Optional[MissingFramesLiteral] = None,
        frame_range: Optional[tuple[int, int]] = None,
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
        # Args for image inputs conversion
        convert_input_images: bool = False,
        input_colorspace: Optional[str] = None,
        color_convert: Optional[tuple[str, str]] = None,
        look: Optional[str] = None,
        display_view: Optional[tuple[str, str]] = None,
        **_) -> None:
    """Convert to movie using ffmpeg

    input_path: set frame number with printf syntax padding (%04d, %06d, etc).
    frame_range: needed for missing frames, first item overrides start_number.
    """

    if isinstance(input_path, str):
        input_path = [input_path]
    if frame_range is not None:
        start_number = frame_range[0]

    def build_drawtext(
            fontfile: str,
            fontsize: str,
            fontcolor: str,
            text: str,
            x: int | str,
            y: int | str,
            start_number: Optional[int] = None) -> str:
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

    def build_filter(command: list) -> None:
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

    def add_frame_rate_and_number(command: list) -> None:
        if frame_rate is not None:
            command.extend(['-framerate', str(frame_rate)])
        if start_number is not None:
            command.extend(['-start_number', str(start_number)])

    # Convert all images to a temporary directory
    tmp_dir = None
    if convert_input_images and '%' in input_path[0]:
        tmp_dir = tempfile.mkdtemp()
        source_dir, source_name = os.path.split(input_path)
        for name in sorted(os.listdir(source_dir)):
            source_path = os.path.join(source_dir, name)
            target_path = os.path.join(
                tmp_dir, _replace_ext(name, temporary_ext))
            convert_image(
                source_path, target_path,
                input_colorspace=input_colorspace,
                color_convert=color_convert,
                look=look,
                display_view=display_view,
                compression=temporary_compression)
        input_path[0] = os.path.join(
            tmp_dir,  _replace_ext(source_name, temporary_ext))

    command = ['ffmpeg']
    if '%' in input_path[0]:
        add_frame_rate_and_number(command)
    for i in input_path:
        command.extend(['-i', i])
        if '%' not in i:
            add_frame_rate_and_number(command)
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
    missing_files = []
    if missing_frames is not None:
        for i in input_path:
            path = generate_missing_frames(
                i, frame_range, start_number, missing_frames)
            if path:
                missing_files.extend(path)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    command.extend([output_path, '-y'])
    subprocess.run(command)
    for f in missing_files:
        os.remove(f)
    if tmp_dir is not None:
        shutil.rmtree(tmp_dir)


def convert_to_gif(
        input_path: str | list[str],
        output_path: str,
        fps: int = 15,
        optimize: bool = True,
        depth: int = 8,
        bounce: bool = False) -> None:
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
