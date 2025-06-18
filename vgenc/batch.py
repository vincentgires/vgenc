#!/usr/bin/env python

import os
import argparse
from .files import get_frame_info
from .convert import convert_image
from ._bpyutils import convert_os_path


def batch_convert_image(
        input_path: str,
        output_path: str,
        frame_range: tuple[int, int],
        frame_jump: int,
        cut: tuple[tuple[int, int]],
        fit: tuple[int, int],
        compression: str,
        data_format: str,
        color_depth: int,
        input_colorspace: str,
        display_view: tuple[str, str]):
    frame_info = get_frame_info(input_path)
    if os.path.splitext(output_path)[1] == '.j2c':
        # Special case for JPEG 2000: openimageio can't create j2c file format
        # and set it's bitrate. Instead, temporary tiff are created from
        # oiiotool and converted with bpy to j2c with cinema bitrate.
        # bpy as convert backend could be used directly without intermediary
        # tiff files and should reduce compute time but the crop and aspect
        # ratio feature needs to be implemented.
        tmp_output = f'{output_path}.tmp.tif'
        convert_image(
            input_path=input_path,
            output_path=tmp_output,
            input_colorspace=input_colorspace,
            display_view=display_view,
            cut=cut,
            fit=fit,
            compression=compression,
            rgb_only=True,
            data_format=data_format,
            image_sequence=True,
            frame_range=frame_range,
            frame_jump=frame_jump)
        convert_image(
            input_path=tmp_output,
            output_path=output_path,
            input_colorspace='Raw',
            display_view=('None', 'Raw'),
            image_sequence=True,
            frame_range=frame_range,
            frame_jump=frame_jump,
            use_bpy=True,
            file_format='JPEG2000',
            color_mode='RGB',
            color_depth=color_depth,
            quality=None,  # Use cinema presets instead
            codec='J2K',
            additional_image_settings={
                'use_jpeg2k_cinema_preset': True,
                'use_jpeg2k_cinema_48': True})
        # Remove temp files
        frame_start, frame_end = frame_range
        for frame in range(frame_start, frame_end + 1):
            file_path = tmp_output.replace(
                '#' * frame_info['digits'],
                f"{frame:0{frame_info['digits']}}")
            if os.path.exists(file_path):
                os.remove(file_path)
    else:
        convert_image(
            input_path=input_path,
            output_path=output_path,
            input_colorspace=input_colorspace,
            display_view=display_view,
            cut=cut,
            fit=fit,
            compression=compression,
            rgb_only=True,
            data_format=data_format,
            image_sequence=True,
            frame_range=frame_range,
            frame_jump=frame_jump)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument(
        'command', help='image')
    parser.add_argument(
        '-i', '--input-path', required=True, metavar='path')
    parser.add_argument(
        '-o', '--output-path', required=True, metavar='path')
    parser.add_argument(
        '-s', '--frame-start', required=True, type=int, metavar='number')
    parser.add_argument(
        '-e', '--frame-end', required=True, type=int, metavar='number')
    parser.add_argument(
        '-j', '--frame-jump', required=True, type=int, metavar='number')
    parser.add_argument(
        '--input-colorspace', required=False, metavar='name')
    parser.add_argument(
        '--display-view', required=True, nargs=2, metavar=('display', 'view'))
    parser.add_argument(
        '--cut-size', required=False, type=int, nargs=2, metavar=('x', 'y'))
    parser.add_argument(
        '--cut-offset', required=False, type=int, nargs=2, metavar=('x', 'y'))
    parser.add_argument(
        '--fit-size', required=False, type=int, nargs=2, metavar=('x', 'y'))
    parser.add_argument(
        '--compression', required=False, metavar='format')
    parser.add_argument(
        '--color-depth', required=True, type=int, metavar='number')
    parser.add_argument(
        '--data-format', required=True, metavar='number')

    args = parser.parse_args()
    match args.command:
        case 'image':
            if all(x is not None for x in (args.cut_size, args.cut_offset)):
                cut = (args.cut_size, args.cut_offset)
            else:
                cut = None
            batch_convert_image(
                input_path=convert_os_path(args.input_path),
                output_path=convert_os_path(args.output_path),
                frame_range=(args.frame_start, args.frame_end),
                frame_jump=args.frame_jump,
                cut=cut,
                fit=args.fit_size,
                compression=args.compression,
                data_format=args.data_format,
                color_depth=args.color_depth,
                input_colorspace=args.input_colorspace,
                display_view=args.display_view)
        case _:
            print('No command are specified')
