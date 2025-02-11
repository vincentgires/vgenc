from subprocess import run, PIPE
import subprocess
import platform
import json

startupinfo = None
if platform.system() == 'Windows':
    # Do not pop window when process is called
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW


def get_movie_size(input_path: str, stream_index: int = 0) -> tuple[int, int]:
    command = [
        'ffprobe', input_path,
        '-show_entries', 'stream=width,height', '-print_format', 'json']
    output = run(
        command, check=True, stdout=PIPE, startupinfo=startupinfo).stdout
    result = json.loads(output.decode())
    size = (
        result['streams'][stream_index]['width'],
        result['streams'][stream_index]['height'])
    return size


def get_movie_duration(input_path: str, stream_index: int = 0) -> int:
    command = [
        'ffprobe', input_path, '-count_packets',
        '-show_entries', 'stream=nb_read_packets', '-print_format', 'json']
    output = run(
        command, check=True, stdout=PIPE, startupinfo=startupinfo).stdout
    result = json.loads(output.decode())
    value = result['streams'][stream_index]['nb_read_packets']
    return int(value)


def get_image_size(input_path: str) -> tuple[int, int]:
    command = ['iinfo', input_path]
    output = run(
        command, check=True, stdout=PIPE, startupinfo=startupinfo).stdout
    x, y = output.decode().split(':')[1].split(',')[0].split('x')
    return int(x), int(y)


def get_metadata_from_movie(input_path: str) -> dict:
    command = ['ffprobe', input_path, '-show_format', '-print_format', 'json']
    output = run(
        command, check=True, stdout=PIPE, startupinfo=startupinfo).stdout
    result = json.loads(output.decode())
    return result['format']['tags']


def get_metadata_from_image(input_path: str) -> dict:
    def get_key(value):
        return value.split(': ')[0].strip()

    def get_value(value):
        value = value.strip()
        key_value = get_key(value)
        start_index = len(key_value) + len(': ')
        value = value[start_index:]
        if value.lstrip('-').isdecimal():
            return int(value)
        elif value.lstrip('-').replace('.', '').isdecimal():
            return float(value)
        elif value.startswith('"') and value.endswith('"'):
            return value[1:-1]
        return value

    command = ['iinfo', '-v', input_path]
    output = run(
        command, check=True, stdout=PIPE, startupinfo=startupinfo).stdout
    return {
        get_key(i): get_value(i)
        for i in output.decode().split('\n') if len(i.split(': ')) > 1}


def get_stream_info(input_path: str) -> dict:
    command = ['ffprobe', input_path, '-show_streams', '-print_format', 'json']
    output = run(
        command, check=True, stdout=PIPE, startupinfo=startupinfo).stdout
    return json.loads(output.decode())


def has_audio_stream(input_path: str) -> bool:
    info_data = get_stream_info(input_path)
    for stream in info_data['streams']:
        if 'codec_type' in stream:
            if stream['codec_type'] == 'audio':
                return True
    return False
