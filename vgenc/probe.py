from subprocess import Popen, PIPE
import json


def get_movie_size(input_path, stream_index=0):
    command = [
        'ffprobe', input_path,
        '-show_entries', 'stream=width,height', '-print_format', 'json']
    with Popen(command, stdout=PIPE, stderr=PIPE) as p:
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
    with Popen(command, stdout=PIPE, stderr=PIPE) as p:
        output, errors = p.communicate()
        output = output.decode()
        output = json.loads(output)
        value = output['streams'][stream_index]['nb_read_packets']
    return int(value)


def get_image_size(input_path):
    command = ['iinfo', input_path]
    with Popen(command, stdout=PIPE, stderr=PIPE) as p:
        output, errors = p.communicate()
        x, y = output.decode().split(':')[1].split(',')[0].split('x')
    return int(x), int(y)


def get_metadata_from_movie(input_path):
    command = ['ffprobe', input_path, '-show_format', '-print_format', 'json']
    with Popen(command, stdout=PIPE, stderr=PIPE) as p:
        output, errors = p.communicate()
        output = output.decode()
        output = json.loads(output)
    return output['format']['tags']


def get_metadata_from_image(input_path: str) -> dict:
    command = ['iinfo', '-v', input_path]
    with Popen(command, stdout=PIPE, stderr=PIPE) as p:
        output, errors = p.communicate()
    return {
        i.split(': ')[0][4:]: i.split(': ')[1][1:-1]
        for i in output.decode().split('\n') if len(i.split(': ')) > 1}
