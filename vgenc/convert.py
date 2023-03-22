import os
import re
import subprocess
from .probe import get_image_size

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


def generate_missing_frames(
        input_path,
        frame_range,
        start_number,
        missing_frames  # previous | black | checkerboard
        ):

    def replace_frame_padding(name, frame, padding):
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
        if missing_frames == 'previous':
            for f in reversed(range(start_number, frame)):
                looked_file = replace_frame_padding(input_path, f, padding)
                if os.path.exists(looked_file):
                    os.symlink(looked_file, target_filepath)
                    break
        elif missing_frames in ('black', 'checkerboard'):
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
                bg_args[missing_frames],
                target_filepath])
        missing_files.append(target_filepath)
    return missing_files


def convert_image(
        input_path,
        output_path,
        colorspace=None,
        look=None,
        image_size=None,
        compression=None,
        **_):
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
        input_path,
        output_path,
        framerate=None,
        start_number=None,
        missing_frames=None,
        frame_range=None,
        video_codec=None,
        video_quality=None,
        video_bitrate=None,
        constrained_quality=None,
        audio_codec=None,
        audio_quality=None,
        audio_bitrate=None,
        resize=None,
        is_stereo=False,
        two_pass=False,
        video_filter=None,
        draw_text=None,
        metadata=None,
        **_):
    """Convert to movie using ffmpeg

    input_path: set frame number with printf syntax padding (%04d, %06d, etc).
    missing_frames: previous, black, checkerboard.
    frame_range: needed for missing frames, first item overrides start_number.
    """

    if isinstance(input_path, str):
        input_path = [input_path]
    if frame_range is not None:
        start_number = frame_range[0]

    def build_drawtext(
            fontfile,
            fontsize,
            fontcolor,
            text,
            x,
            y,
            start_number=None):
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

    def build_filter(command):
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
    missing_files = []
    if missing_frames is not None:
        for i in input_path:
            path = generate_missing_frames(
                i, frame_range, start_number, missing_frames)
            if path:
                missing_files.extend(path)
    command.extend([output_path, '-y'])
    subprocess.run(command)
    for f in missing_files:
        os.remove(f)


def convert_to_gif(
        input_path,
        output_path,
        fps=15,
        optimize=True,
        depth=8,
        bounce=False):
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
