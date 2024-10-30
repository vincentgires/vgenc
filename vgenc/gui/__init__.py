from typing import TypedDict
import re

input_colorspaces = [
    'ACES2065-1',  # Default one
    'ACEScg',
    'Linear sRGB',
    'sRGB - Texture']
resolutions = {
    '2k Full': {
        'cut': (2048, 1080)},
    '2k Univisium': {
        'cut': (2048, 1024)},
    '2k Full Univisium Letterbox': {
        'cut': (2048, 1024),
        'fit': (2048, 1080)},
    '2k Scope': {
        'cut': (2048, 858)},
    '2k Flat': {
        'cut': (1998, 1080)},
    '2k Flat Univisium Letterbox': {
        'cut': (2048, 1024),
        'fit': (1998, 1080)},
    'HD': {
        'cut': (1920, 1080)},
    'HD Univisium Letterbox': {
        'cut': (2048, 1024),
        'fit': (1920, 1080)},
    'HD Scope Letterbox': {
        'cut': (2048, 858),
        'fit': (1920, 1080)},
    'HD Full Letterbox': {
        'cut': (2048, 1080),
        'fit': (1920, 1080)},
    'HD Flat Letterbox': {
        'cut': (1998, 1080),
        'fit': (1920, 1080)},
    'DVD PAL Univisium Letterbox': {
        'cut': (2048, 1024),
        'fit': (720, 576)},
    'DVD PAL Scope Letterbox': {
        'cut': (2048, 858),
        'fit': (720, 576)}}
file_formats = {
    'JPEG': {
        'compression': 'jpeg:95',
        'ext': '.jpg',
        'color_depths': ['8 bits']},
    'JPEG 2000': {
        'ext': '.j2c',
        'color_depths': ['8 bits', '12 bits', '16 bits integer']},
    'DPX': {
        'ext': '.dpx',
        'color_depths': ['8 bits', '10 bits', '12 bits', '16 bits integer']},
    'Open EXR': {
        'ext': '.exr',
        'color_depths': ['16 bits float', '32 bits float']},
    'TIFF': {
        'compression': 'none',
        'ext': '.tif',
        'color_depths': ['8 bits', '16 bits integer']},
    'Targa': {
        'compression': 'none',
        'ext': '.tga',
        'color_depths': ['8 bits']}}
color_depths = {
    '8 bits': (8,),
    '10 bits': (10,),
    '12 bits': (12,),
    '16 bits integer': (16, 'integer'),
    '16 bits float': (16, 'float'),
    '32 bits float': (32, 'float')}
view_transforms = {
    'Rec. 709': (
        'Rec.1886 Rec.709',
        'ACES 1.0 - SDR Video'),
    'Rec. 2020': (
        'Rec.1886 Rec.2020',
        'ACES 1.1 - SDR Video (Rec.709 lim)'),
    'Rec. 2100': (
        'Rec.2100-PQ',
        'ACES 1.1 - HDR Video (1000 nits & Rec.2020 lim)'),
    'P3-DCI': (
        'P3-DCI',
        'ACES 1.1 - SDR Cinema (D65 sim on DCI)'),
    'DCDM': (
        'XYZ',
        'DCDM'),
    'sRGB': (
        'sRGB',
        'ACES 1.0 - SDR Video')}
movie_containers = {
    'MPEG-4': {
        'ext': '.mp4',
        'codecs': ['H264', 'H265', 'MJPEG']},
    'Quicktime': {
        'ext': '.mov',
        'codecs': ['H264', 'MJPEG', 'ProRes 422 HQ', 'ProRes 4444']},
    'WebM': {
        'ext': '.webm',
        'codecs': ['VP9']},
    'Matroska': {
        'ext': '.mkv'},
    'Ogg': {
        'ext': '.ogg',
        'codecs': ['Theora']},
    'MXF': {
        'ext': '.mxf',
        'codecs': ['ProRes 422 HQ', 'ProRes 4444']}}
movie_codecs = {
    'H264': {
        'codec': 'h264',
        'crf': 25,
        'bitrate': 0},
    'H265': {
        'codec': 'h265',
        'crf': 25,
        'bitrate': 0},
    'ProRes 422 HQ': {
        'codec': 'prores',
        'profile': '3',
        'pixel_format': 'yuv422p10le'},
    'ProRes 4444': {
        'codec': 'prores',
        'profile': '4',
        'pixel_format': 'yuva444p10le'},
    'VP9': {
        'codec': 'vp9',
        'crf': 25,
        'bitrate': 0},
    'AV1': {
        'codec': 'av1',
        'crf': 25,
        'bitrate': 0},
    'MJPEG': {
        'codec': 'mjpeg',
        'quality': 2},
    'Theora': {
        'codec': 'theora',
        'quality': 7}}
audio_codecs = {
    'Copy': {
        'codec': 'copy'},
    'FLAC': {
        'codec': 'flac'},
    'OPUS': {
        'codec': 'libopus'},
    'Vorbis': {
        'codec': 'libvorbis'},
    'MP3': {
        'codec': 'libmp3lame'}}

oiiotool_bit_depths = {
    (8,): 'uint8',
    (10,): 'uint10',
    (12,): 'uint12',
    (16, 'integer'): 'uint16',
    (16, 'float'): 'half',
    (32, 'float'): 'float'}

SelectionDataType = TypedDict('Data', {
    'resolution': str | None,
    'file_format': str | None,
    'color_depth': str | None,
    'view_transform': str | None,
    'audio_codec': str | None,
    'movie_container': str | None,
    'movie_codec': str | None})


def find_views_paths(path: str) -> list[tuple[str, str]] | None:
    # Find %v{name1|name2|etc}
    pattern = r'%v\{([^}]+)\}'
    if matches := re.findall(pattern, path):
        views = set([x for match in matches for x in match.split('|')])
        return [(view, re.sub(pattern, view, path)) for view in views]
