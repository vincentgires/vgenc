#!/usr/bin/env python

import argparse
from .convert import convert_image, convert_image_sequence_to_movie

parser = argparse.ArgumentParser()
parser.add_argument(
    'command', help='image, movie')
parser.add_argument(
    '-i', '--input-path', required=True, nargs='+', metavar='path')
parser.add_argument(
    '-o', '--output-path', required=True, metavar='path')
# Convert image arguments
parser.add_argument(
    '--colorspace', required=False, nargs=2, metavar=('input', 'output'))
parser.add_argument(
    '--look', required=False, metavar='name')
parser.add_argument(
    '--image-size', required=False, type=int, nargs=2, metavar=('x', 'y'))
parser.add_argument(
    '--compression', required=False, metavar='format')
# Convert video
parser.add_argument(
    '--framerate', required=False, type=int, metavar='number')
parser.add_argument(
    '--start-number', required=False, type=int, metavar='number')
parser.add_argument(
    '-vc', '--video-codec', required=False, metavar='name')
parser.add_argument(
    '-vq', '--video-quality', required=False, type=int, metavar='number')
parser.add_argument(
    '-vb', '--video-bitrate', required=False, metavar='value')
parser.add_argument(
    '-cq', '--constrained-quality', required=False, type=int, metavar='number')
parser.add_argument(
    '-ac', '--audio-codec', required=False, metavar='name')
parser.add_argument(
    '-aq', '--audio-quality', required=False, type=int, metavar='number')
parser.add_argument(
    '-ab', '--audio-bitrate', required=False, metavar='value')
parser.add_argument(
    '--resize', required=False, type=int, nargs=2, metavar=('x', 'y'))
parser.add_argument(
    '--is-stereo', action='store_true', required=False)
parser.add_argument(
    '--two-pass', action='store_true', required=False)

args = parser.parse_args()
match args.command:
    case 'image':
        convert_image(**vars(args))
    case 'movie':
        convert_movie(**vars(args))
    case _:
        print('No command are specified')
