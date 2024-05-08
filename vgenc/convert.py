import os
import tempfile
import shutil
from subprocess import run
from typing import Optional
from .files import (
    MissingFramesLiteral, get_frame_info, generate_missing_frames)
try:
    import bpy  # Can be used as backend but shouldn't be mandatory
except ImportError:
    ...

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


def convert_image(
        input_path: str,
        output_path: str,
        input_colorspace: Optional[str] = None,
        look: Optional[str] = None,
        display_view: Optional[tuple[str, str]] = None,
        resize: Optional[tuple[int, int]] = None,
        compression: Optional[str | int] = None,
        rgb_only: bool = False,
        # Image sequence arguments
        image_sequence: bool = False,
        frame_range: tuple[int, int] = (1, 1),
        frame_jump: int = 1,
        # oiiotool options
        color_convert: Optional[tuple[str, str]] = None,
        data_format: Optional[str | list] = None,
        # bpy options
        use_bpy: bool = False,
        file_format: Optional[str] = None,
        color_mode: Optional[str] = None,
        color_depth: Optional[int] = None,
        quality: Optional[int] = None,
        codec: Optional[str] = None,
        **_) -> None:
    """Convert image using oiiotool or bpy

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
                resize=resize,
                compression=compression,
                rgb_only=rgb_only,
                data_format=data_format)
        return

    if use_bpy:
        codec_attributes = {
            'JPEG2000': 'jpeg2k_codec',
            'OPEN_EXR': 'exr_codec',
            'OPEN_EXR_MULTILAYER': 'exr_codec',
            'TIFF': 'tiff_codec'}
        data = bpy.data
        image = data.images.load(input_path)
        if input_colorspace is not None:
            image.colorspace_settings.name = input_colorspace
        if resize is not None:
            image.scale(*resize)
        if display_view is None:
            if file_format is not None:
                image.file_format = file_format.upper()
            image.save(filepath=output_path)
        else:
            scene = bpy.context.scene
            if look is not None:
                scene.view_settings.look = look
            display, view = display_view
            scene.display_settings.display_device = display
            scene.view_settings.view_transform = view
            image_settings = scene.render.image_settings
            if file_format is not None:
                image_settings.file_format = file_format.upper()
            if color_mode is not None:
                image_settings.color_mode = color_mode.upper()
            elif rgb_only:
                image_settings.color_mode = 'RGB'
            if color_depth is not None:
                image_settings.color_depth = str(color_depth)
            if compression is not None:
                image_settings.compression = compression
            if quality is not None:
                image_settings.quality = quality
            if codec is not None:
                if codec_attribute := codec_attributes.get(
                        image_settings.file_format):
                    setattr(image_settings, codec_attribute, codec.upper())
            image.save_render(filepath=output_path)
        data.images.remove(image)
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
    if resize is not None:
        x, y = resize
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
    run(command)


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
        run(first_pass_command)
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
    run(command)
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
    run(command)


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
