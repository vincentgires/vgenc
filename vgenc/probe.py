from subprocess import Popen, PIPE
import json


def get_movie_size(input_path, stream_index=0):
    command = [
        'ffprobe', input_path,
        '-show_entries', 'stream=width,height', '-print_format', 'json']
    p = Popen(command, stdout=PIPE, stderr=PIPE)
    p.wait()
    output, errors = p.communicate()
    output = output.decode()
    output = json.loads(output)
    size = (
        output['streams'][stream_index]['width'],
        output['streams'][stream_index]['height'])
    return size


def get_movie_duration(input_path, stream_index=0):
    command = [
        'ffprobe', input_path, '-count_packets',
        '-show_entries', 'stream=nb_read_packets', '-print_format', 'json']
    p = Popen(command, stdout=PIPE, stderr=PIPE)
    p.wait()
    output, errors = p.communicate()
    output = output.decode()
    output = json.loads(output)
    value = output['streams'][stream_index]['nb_read_packets']
    return int(value)


def get_image_size(input_path):
    command = ['iinfo', input_path]
    p = Popen(command, stdout=PIPE, stderr=PIPE)
    p.wait()
    output, errors = p.communicate()
    x, y = output.decode().split(':')[1].split(',')[0].split('x')
    return int(x), int(y)


def get_metadata_from_movie(input_path):
    command = ['ffprobe', input_path, '-show_format', '-print_format', 'json']
    p = Popen(command, stdout=PIPE, stderr=PIPE)
    p.wait()
    output, errors = p.communicate()
    output = output.decode()
    output = json.loads(output)
    return output['format']['tags']


def get_metadata_from_image(input_path):
    command = ['iinfo', '-v', input_path]
    p = Popen(command, stdout=PIPE, stderr=PIPE)
    p.wait()
    output, errors = p.communicate()
    return {
        i.split(': ')[0][4:]: i.split(': ')[1][1:-1]
        for i in output.decode().split('\n') if len(i.split(': ')) > 1}


def get_stream_info(input_path):
    command = ['ffprobe', input_path, '-show_streams', '-print_format', 'json']
    p = Popen(command, stdout=PIPE, stderr=PIPE)
    p.wait()
    output, errors = p.communicate()
    output = output.decode()
    output = json.loads(output)
    return output


def has_audio_stream(input_path):
    info_data = get_stream_info(input_path)
    for stream in info_data['streams']:
        if 'codec_type' in stream:
            if stream['codec_type'] == 'audio':
                return True
    return False
