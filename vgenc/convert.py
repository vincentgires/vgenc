import os
import tempfile
import shutil
import logging
from pathlib import Path
from tempfile import NamedTemporaryFile
from subprocess import run
from typing import Literal
from .files import (
    MissingFramesLiteral, get_frame_info, generate_missing_frames)
from .probe import get_image_size
try:
    import bpy  # Can be used as backend but shouldn't be mandatory
    from ._bpyutils import (
        set_render_settings as set_bpy_render_settings,
        load_image_sequence_strip as load_bpy_image_sequence_strip,
        create_text_strips_by_ranges as create_bpy_text_strips_by_ranges,
        create_text_strip as create_bpy_text_strip)
    from .files import (
        find_frame_mapping_from_hash_pattern, fill_missing_images)
except ImportError:
    ...

ffmpeg_video_codecs = {
    'copy': 'copy',
    'vp9': 'libvpx-vp9',
    'av1': 'libaom-av1',
    'theora': 'libtheora',
    'mjpeg': 'mjpeg',
    'h264': 'libx264',
    'h265': 'libx265',
    'prores': 'prores_ks'}
ffmpeg_audio_codecs = {
    'copy': 'copy',
    'flac': 'flac',
    'opus': 'libopus',
    'vorbis': 'libvorbis',
    'mp3': 'libmp3lame'}
ffmpeg_color_options = {
    'mjpeg': {
        'colorspace': {
            'rgb': 2,
            'bt601': 5,
            'bt709': 1},
        'primaries': {
            'rgb': 2,
            'bt601': 5,
            'bt709': 1},
        'transfert': {
            'linear': 1,
            'gamma22': 4,
            'bt709': 2,
            'srgb': 13}},
    'libx264': {
        'colorspace': {
            'rgb': 2,
            'bt601': 5,
            'bt709': 1,
            'bt2020': 9},
        'primaries': {
            'rgb': 2,
            'bt601': 5,
            'bt709': 1,
            'bt2020': 9},
        'transfert': {
            'linear': 1,
            'gamma22': 4,
            'bt709': 2,
            'srgb': 13}},
    'libx265': {
        'colorspace': {
            'rgb': 2,
            'bt601': 5,
            'bt709': 1,
            'bt2020': 9},
        'primaries': {
            'rgb': 2,
            'bt601': 5,
            'bt709': 1,
            'bt2020': 9},
        'transfert': {
            'linear': 1,
            'gamma22': 4,
            'bt709': 2,
            'srgb': 13,
            'pq': 16,
            'hlg': 14}},
    'libvpx-vp9': {
        'colorspace': {
            'rgb': 2,
            'bt601': 5,
            'bt709': 1,
            'bt2020': 9},
        'primaries': {
            'rgb': 2,
            'bt601': 5,
            'bt709': 1,
            'bt2020': 9},
        'transfert': {
            'linear': 1,
            'gamma22': 4,
            'bt709': 2,
            'srgb': 13}}}

temporary_ext = '.jpg'
temporary_compression = 'jpeg:95'


def _get_ffmpeg_color_option(
        value: str | int,
        codec: str | None = None,
        option: str | None = None):
    if isinstance(value, int):
        return value
    if options := ffmpeg_color_options.get(codec):
        if values := options.get(option):
            return values.get(value)


def convert_image(
        input_path: str,
        output_path: str,
        input_colorspace: str | None = None,
        look: str | None = None,
        display_view: tuple[str, str] | None = None,
        resize: tuple[int, int] | None = None,
        compression: str | int | None = None,
        rgb_only: bool = False,
        # Image sequence arguments
        image_sequence: bool = False,
        frame_range: tuple[int, int] = (1, 1),
        frame_jump: int = 1,
        # oiiotool options
        oiiotool_bin: str = 'oiiotool',
        auto_cut: bool = False,
        cut: tuple[tuple[int, int]] | None = None,
        crop: tuple[tuple[int, int]] | None = None,
        fit: tuple[int, int] | None = None,
        color_convert: tuple[str, str] | None = None,
        data_format: str | list | None = None,
        # bpy options
        use_bpy: bool = False,
        file_format: str | None = None,
        color_mode: str | None = None,
        color_depth: int | None = None,
        quality: int | None = None,
        codec: str | None = None,
        additional_image_settings: dict | None = None,
        **_) -> None:
    """Convert image using oiiotool or bpy

    Args:
        input_colorspace: needed for display_view
        auto_cut: resize is mandatory
    """

    if image_sequence:
        def build_path(path: str, frame: int) -> str:
            frame_info = get_frame_info(path)
            frame_path = (
                f"{frame_info['start']}"
                f"{frame:0{frame_info['digits']}}"
                f"{frame_info['end']}")
            return frame_path

        frame_start, frame_end = frame_range
        all_frames = range(frame_start, frame_end + 1, frame_jump)
        for index, frame in enumerate(all_frames):
            convert_image(
                input_path=build_path(input_path, frame=frame),
                output_path=build_path(output_path, frame=frame),
                input_colorspace=input_colorspace,
                color_convert=color_convert,
                look=look,
                display_view=display_view,
                resize=resize,
                compression=compression,
                rgb_only=rgb_only,
                auto_cut=auto_cut,
                cut=cut,
                crop=crop,
                fit=fit,
                data_format=data_format,
                use_bpy=use_bpy,
                file_format=file_format,
                color_mode=color_mode,
                color_depth=color_depth,
                quality=quality,
                codec=codec)
            percentage = ((index + 1) * 100) / len(all_frames)
            print(f'Progress: {round(percentage)}%')
        return

    if use_bpy:
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
            set_bpy_render_settings(
                scene=scene,
                look=look,
                display_view=display_view,
                file_format=file_format,
                color_mode=(
                    color_mode if not None else 'RGB' if rgb_only else None),
                color_depth=color_depth,
                compression=compression,
                quality=quality,
                codec=codec,
                additional_image_settings=additional_image_settings)
            image.save_render(filepath=output_path)
        print(f'bpy: {output_path}')
        data.images.remove(image)
        return

    command = [oiiotool_bin, '-v']
    if rgb_only:
        command.append('-i:ch=R,G,B')
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
    if auto_cut and resize is not None:
        input_x, input_y = get_image_size(input_path)
        resize_x, resize_y = resize
        cut_offset = (
            int((input_x - resize_x) / 2),
            int((input_y - resize_y) / 2))
        cut = (resize, cut_offset)
    if cut is not None:
        cut_size, cut_offset = cut
        cut_size = 'x'.join(str(i) for i in cut_size)
        cut_offset = '+'.join(str(i) for i in cut_offset)
        command.extend(['--cut', f'{cut_size}+{cut_offset}'])
    if crop is not None:
        crop_size, crop_offset = crop
        crop_size = 'x'.join(str(i) for i in crop_size)
        crop_offset = '+'.join(str(i) for i in crop_offset)
        command.extend(['--crop', f'{crop_size}+{crop_offset}'])
    if fit is not None:
        fx, fy = fit
        command.extend(['--fit', f'{fx}x{fy}'])
    if resize is not None:
        rx, ry = resize
        command.extend(['--resize', f'{rx}x{ry}'])
    if compression is not None:
        command.extend(['--compression', compression])
    if data_format is not None:
        # Can set a single data format or a list to specify channel formats
        # -d half -d Z=float
        df = [data_format] if isinstance(data_format, str) else data_format
        for d in df:
            command.extend(['-d', d])
    command.extend(['-o', output_path])
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    run(command)
    if os.path.exists(output_path):
        print(f'{output_path} is generated.')
    else:
        logging.error(f'{output_path} was not able to be generated.')


def _replace_ext(file_path: str, ext: str) -> str:
    path, old_ext = os.path.splitext(file_path)
    return path + ext


def convert_tx(
        input_path: str,
        output_path: str | None = None,
        color_convert: tuple[str, str] | None = None,
        file_format: Literal['openexr', 'tiff'] | None = None,
        metadata: dict[str, str | int] | None = None,
        overwrite=False) -> str | None:
    """Convert texture to TX using maketx

    Args:
        input_path: source image path
        output_path: output image path (or None and .tx will be created in the
          same directory)
        color_convert: input / target colorspace (or None will try to guess it
          from file extension)
        file_format: file format name (openexr or tiff)
        metadata: add metadata
        overwrite: overwrite output file

    Returns:
        The .tx path if it already exists, or the generated one
    """

    if not os.path.exists(input_path):
        return
    _, ext = os.path.splitext(input_path)
    if ext == '.tx':  # Don't convert tx
        return input_path
    tx_path = output_path or _replace_ext(input_path, ext='.tx')
    if os.path.exists(tx_path) and not overwrite:  # Don't overwrite
        return tx_path
    command = ['maketx', input_path]
    if color_convert is not None:
        command.extend(['--colorconvert', *color_convert])
    if file_format is not None:
        command.extend(['--format', file_format])
    if metadata is not None:
        for md, mdv in metadata.items():
            attrib_arg = '--sattrib' if isinstance(mdv, str) else '--attrib'
            command.extend([attrib_arg, md, mdv])
    command.extend(['-o', tx_path])
    run(command)
    return tx_path


def write_ffmpeg_sendcmd(
        frame_data: dict[int, str],
        frame_rate: int,
        output_path: str):
    """Generate an ffmpeg sendcmd file for dynamic drawtext
    """
    dt = 1 / frame_rate  # frame time in seconds

    def escape_text(text):
        return text.replace('\\', '\\\\').replace(':', '\\:')

    lines = []
    for frame_num, text in sorted(frame_data.items()):
        # ts = f'{frame_num * dt:.6f}'  # timestamp with microseconds
        # Offset by half a frame so the text appears visible on the intended
        # frame. FFmpeg applies `sendcmd` changes from the given timestamp, not
        # before. This ensures the text is visible exactly when the frame
        # starts.
        ts = f'{max((frame_num - 0.5) * dt, 0):.6f}'
        safe_text = escape_text(text)
        line = f"{ts} drawtext reinit text='{safe_text}';"
        lines.append(line)
    output_path = Path(output_path)
    output_path.write_text('\n'.join(lines), encoding='utf-8')


def convert_movie(
        input_path: str | list[str],
        output_path: str,
        frame_rate: int | None = None,
        start_number: int | None = None,
        missing_frames: MissingFramesLiteral | None = None,
        frame_range: tuple[int, int] | None = None,
        video_codec: str | None = None,
        video_profile: str | None = None,
        video_quality: int | None = None,
        video_bitrate: int | None = None,
        constrained_quality: int | None = None,
        colorspace: str | int | None = None,
        color_primaries: str | int | None = None,
        color_transfer: str | int | None = None,
        pixel_format: str | None = None,
        audio_codec: str | None = None,
        audio_quality: int | None = None,
        audio_bitrate: str | None = None,
        resize: tuple[int, int] | None = None,
        is_stereo: bool = False,
        two_pass: bool = False,
        video_filter: dict | list[dict] | None = None,
        draw_text: dict | list[dict] | None = None,
        metadata: dict | None = None,
        # Args for image inputs conversion
        convert_input_images: bool = False,
        input_colorspace: str | None = None,
        color_convert: tuple[str, str] | None = None,
        look: str | None = None,
        display_view: tuple[str, str] | None = None,
        # bpy options
        use_bpy: bool = False,
        working_colorspace: str | None = None,
        file_format: str | None = None,
        color_mode: str | None = None,
        color_depth: int | None = None,
        compression: int | None = None,
        quality: int | None = None,
        codec: str | None = None,
        additional_image_settings: dict | None = None,
        resolution: tuple[int, int] | None = None,
        scale: tuple[int, int] | None = None,
        crop:  tuple[int, int, int, int] | None = None,
        _keep_data: bool = False,
        _render: bool = True,
        **_) -> None:
    """Convert to movie using ffmpeg or bpy

    Args:
        input_path:
          ffmpeg: set frame number with printf syntax padding (%04d, %06d, etc)
          bpy: set frame number with hash pattern (###, ####, etc)
        frame_range:
          needed for missing frames, first item overrides start_number
    """

    if use_bpy:
        directory, frame_mapping = find_frame_mapping_from_hash_pattern(
            path=input_path)
        images = fill_missing_images(frame_mapping, *frame_range)
        scene = bpy.data.scenes.new('Convert')
        if working_colorspace is not None:
            scene.sequencer_colorspace_settings.name = working_colorspace
        channel = 1
        strip = load_bpy_image_sequence_strip(
            scene=scene,
            directory=directory,
            images=images,
            frame_range=frame_range,
            channel=channel,
            colorspace=input_colorspace,
            set_scene_resolution=False if resolution is None else True)
        if scale is not None:
            strip.transform.scale_y, strip.transform.scale_x = scale
        if crop is not None:
            left, right, top, bottom = crop
            strip.crop.min_x = left
            strip.crop.max_x = right
            strip.crop.max_y = top
            strip.crop.min_y = bottom
        set_bpy_render_settings(
            scene=scene,
            look=look,
            display_view=display_view,
            file_format=file_format,
            color_mode=color_mode,
            color_depth=color_depth,
            compression=compression,
            quality=quality,
            codec=codec,
            additional_image_settings=additional_image_settings,
            resolution=resolution)
        if frame_rate is not None:
            scene.render.fps = frame_rate
            scene.render.fps_base = 1
        fonts = []
        if draw_text is not None:
            for text_data in draw_text:
                if font_path := text_data.get('font_path'):
                    font = bpy.data.fonts.load(font_path)
                    fonts.append(font)
                else:
                    font = None
                channel += 1
                text = text_data.get('text')
                if isinstance(text, list):
                    create_bpy_text_strips_by_ranges(
                        scene=scene,
                        text_ranges=text,
                        channel=channel,
                        location=text_data.get('location'),
                        font_size=text_data.get('font_size'),
                        color=text_data.get('color'),
                        font=font,
                        anchor_x=text_data.get('anchor_x'),
                        anchor_y=text_data.get('anchor_y'))
                else:
                    create_bpy_text_strip(
                        scene=scene,
                        text=text,
                        frame_range=(frame_range[0], frame_range[1] + 1),
                        channel=channel,
                        location=text_data.get('location'),
                        font_size=text_data.get('font_size'),
                        color=text_data.get('color'),
                        font=font,
                        anchor_x=text_data.get('anchor_x'),
                        anchor_y=text_data.get('anchor_y'))

        # Render
        if output_path:
            scene.render.filepath = output_path
        if _render:
            bpy.ops.render.render(animation=True, scene=scene.name)

        # Delete scene
        if not _keep_data:
            bpy.data.scenes.remove(scene)
            for font in fonts:
                bpy.data.fonts.remove(font)

        return

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
            start_number: int | None = None) -> str:
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
    for i in input_path:
        if '%' in i:
            # For image sequence
            add_frame_rate_and_number(command)
        command.extend(['-i', i])
    if all('%' not in i for i in input_path):
        # For movie output
        add_frame_rate_and_number(command)
    vc = ffmpeg_video_codecs.get(video_codec, video_codec)
    if video_codec is not None:
        command.extend(['-c:v', vc])
        if video_codec in ('prores', 'prores_ks', ):
            command.extend(['-vendor', 'apl0'])  # Treat the file as if it was
            # created by the Apple ProRes encoder
    if video_profile is not None:
        command.extend(['-profile:v', video_profile])
    if video_quality is not None:
        command.extend(['-q:v', str(video_quality)])
    if constrained_quality is not None:
        command.extend(['-crf', str(constrained_quality)])
    if video_bitrate is not None:
        # to enable constant quality instead of constrained quality, bitrate
        # should be set to 0.
        command.extend(['-b:v', str(video_bitrate)])
    if pixel_format is not None:
        command.extend(['-pix_fmt', pixel_format])
    # Color options
    if colorspace is not None:
        cs = _get_ffmpeg_color_option(
            value=colorspace, codec=vc, option='colorspace')
        if cs is not None:
            command.extend(['-colorspace', str(cs)])
    if color_primaries is not None:
        cp = _get_ffmpeg_color_option(
            value=color_primaries, codec=vc, option='primaries')
        if cp is not None:
            command.extend(['-color_primaries', str(cp)])
    if color_transfer is not None:
        ct = _get_ffmpeg_color_option(
            value=color_transfer, codec=vc, option='transfert')
        if ct is not None:
            command.extend(['-color_trc', str(ct)])
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


def convert_gif(
        input_path: str | list[str],
        output_path: str,
        fps: int = 15,
        optimize: bool = True,
        depth: int = 8,
        bounce: bool = False) -> None:
    """Convert images to gif

    Args:
        input_path: it can be a folder directory or list of image paths
    """

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


def concatenate(input_paths: list[str], output_path: str):
    """Concatenate a list of files

    Args:
        input_paths: list of inputs
        output_path: concatenated file
    """
    with NamedTemporaryFile() as temp_f:
        for path in input_paths:
            line = f"file '{os.path.abspath(path)}'\n"
            temp_f.write(line.encode())
        temp_f.flush()
        command = [
            'ffmpeg', '-y',
            '-f', 'concat',
            '-safe', '0',
            '-i', temp_f.name,
            '-c:v', 'copy',
            '-c:a', 'copy',
            output_path]
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
            'pad': 'in_w:in_h+100:0:-50'})

if __name__ == '__main__':
    # Example with bpy:
    convert_movie(
        input_path='input.####.png',
        output_path='output.####.tif',
        frame_range=(101, 200),
        input_colorspace='Raw',
        display_view=('None', 'Raw'),
        use_bpy=True,
        scale=(0.940, 0.940),
        crop=(0, 0, 28, 28),
        resolution=(1920, 1020),
        file_format='TIFF',
        color_mode='RGB',
        color_depth=8,
        additional_image_settings={'tiff_codec': 'NONE'},
        draw_text=[
            {'text': 'fixed text',
             'font_path': 'font.ttf',
             'font_size': 20,
             'location': (0.0, 1.0),
             'color': (1.0, 1.0, 1.0, 1.0),
             'anchor_x': 'LEFT',
             'anchor_y': 'TOP'},
            {'text': [
                (101, 150, 'range text 1 {frame}'),
                (150, 190, 'range text 2'),
                (190, 190 + 1, 'range text 3')],
             'font_path': 'font.ttf',
             'font_size': 20,
             'location': (0.0, 0.0),
             'color': (1.0, 1.0, 1.0, 1.0),
             'anchor_x': 'LEFT',
             'anchor_y': 'BOTTOM'}])
