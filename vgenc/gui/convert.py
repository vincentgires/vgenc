# TODO: add ocio looks
# TODO: read ocio config for listing colorspaces, view transforms and looks

import os
from tkinter import Tk, Listbox, Entry, Button, Frame, StringVar, OptionMenu
from tkinter.filedialog import askopenfilename, askdirectory
from functools import partial
from typing import Callable, Iterable
from ..convert import convert_image, convert_movie
from ..files import get_frame_info, find_image_sequence_range
from ..probe import get_image_size

input_colorspaces = [
    'ACES2065-1',
    'ACEScg',
    'Linear sRGB',
    'sRGB - Texture']
resolutions = {
    '2k full': {'cut': (2048, 1080)},
    '2k scope': {'cut': (2048, 858)},
    '2k flat': {'cut': (1998, 1080)},
    'HD scope letterbox': {'cut': (2048, 858), 'fit': (1920, 1080)},
    'DVD PAL scope letterbox': {'cut': (2048, 858), 'fit': (720, 576)}}
file_formats = {
    'JPEG': {'compression': 'jpeg:95', 'ext': '.jpg'},
    'JPEG 2000': {'ext': '.j2c'},
    'DPX': {'ext': '.dpx'},
    'Open EXR': {'ext': '.exr'},
    'TIFF': {'compression': 'none', 'ext': '.tif'}}
color_depths = {
    '8 bits': 8,
    '10 bits': 10,
    '12 bits': 12,
    '16 bits integer': (16, 'integer'),
    '16 bits float': (16, 'float'),
    '32 bits float': 32}
view_transforms = {
    'Rec. 709': ('Rec.1886 Rec.709', 'ACES 1.0 - SDR Video'),
    'DCDM': ('XYZ', 'DCDM'),
    'ACES2065-1': None,
    'sRGB': ('sRGB', 'ACES 1.0 - SDR Video')}
movie_formats = {
    'MP4/H264': {'codec': 'h264', 'ext': '.mp4', 'crf': 25, 'bitrate': 0},
    'MP4/H265': {'codec': 'h265', 'ext': '.mp4', 'crf': 25, 'bitrate': 0},
    'WebM/VP9': {'codec': 'vp9', 'ext': '.webm', 'crf': 25, 'bitrate': 0},
    'MKV/MJPEG': {'codec': 'mjpeg', 'ext': '.mkv', 'quality': 2}}

_oiiotool_bit_depths = {
    8: 'uint8',
    10: 'uint10',
    12: 'uint12',
    (16, 'integer'): 'uint16',
    (16, 'float'): 'half',
    32: 'float'}


def convert():
    data = get_all_selection()
    input_path = os.path.expandvars(input_entry.get())
    output_path = os.path.expandvars(output_entry.get())
    frame_info = get_frame_info(input_path)
    if frame_info is None:
        return
    input_range = find_image_sequence_range(
        path=input_path,
        digits=frame_info['digits'],
        prefix=frame_info['start'],
        suffix=frame_info['end'])
    if input_range is None:
        return

    first_frame_path = (
        f"{frame_info['start']}"
        f"{input_range[0]:0{frame_info['digits']}}"
        f"{frame_info['end']}")
    input_x, input_y = get_image_size(first_frame_path)

    for resolution in data['resolutions']:
        if cut := resolutions[resolution].get('cut'):
            cut_x, cut_y = cut
            cut_offset = (
                int((input_x - cut_x) / 2),
                int((input_y - cut_y) / 2))
            cut = ((cut_x, cut_y), cut_offset)
        fit = resolutions[resolution].get('fit')

        for file_format in data['file_formats']:
            file_ext = file_formats[file_format]['ext']
            file_compression = file_formats[file_format].get('compression')

            for color_depth in data['color_depths']:
                color_depth_value = color_depths[color_depth]
                oiio_color_depth = _oiiotool_bit_depths[color_depth_value]

                for view_transform in data['view_transforms']:
                    display_view = view_transforms[view_transform]
                    expanded_output_dir = output_path.format(
                        resolution=resolution,
                        file_format=file_format,
                        color_depth=color_depth,
                        view_transform=view_transform)
                    output_image = os.path.join(
                        expanded_output_dir,
                        f"image.{'#' * frame_info['digits']}{file_ext}")

                    # Special case for JPEG 2000: openimageio can't create j2c
                    # file format and set it's bitrate. Instead, temporary tiff
                    # are created from oiiotool and converted with bpy to j2c
                    # with cinema bitrate.
                    # bpy as convert backend could be used directly without
                    # intermediary tiff files and should reduce compute time
                    # but the crop and aspect ratio feature needs to be
                    # implemented.
                    if file_format == 'JPEG 2000':
                        tmp_output = f'{output_image}.tmp.tif'
                        convert_image(
                            input_path=input_path,
                            output_path=tmp_output,
                            input_colorspace=input_colorspace_variable.get(),
                            display_view=display_view,
                            cut=cut,
                            resize=fit,
                            compression=file_compression,
                            rgb_only=True,
                            data_format=oiio_color_depth,
                            frame_range=input_range,
                            image_sequence=True)
                        convert_image(
                            input_path=tmp_output,
                            output_path=output_image,
                            input_colorspace='Raw',
                            display_view=('None', 'Raw'),
                            data_format=oiio_color_depth,
                            frame_range=input_range,
                            image_sequence=True,
                            use_bpy=True,
                            file_format='JPEG2000',
                            color_mode='RGB',
                            color_depth=color_depth_value,
                            quality=None,  # Use cinema presets instead
                            codec='J2K',
                            additional_image_settings={
                                'use_jpeg2k_cinema_preset': True,
                                'use_jpeg2k_cinema_48': True})
                        # Remove temp files
                        frame_start, frame_end = input_range
                        for frame in range(frame_start, frame_end + 1):
                            file_path = tmp_output.replace(
                                '#' * frame_info['digits'],
                                f"{frame:0{frame_info['digits']}}")
                            if os.path.exists(file_path):
                                os.remove(file_path)
                    else:
                        convert_image(
                            input_path=input_path,
                            output_path=output_image,
                            input_colorspace=input_colorspace_variable.get(),
                            display_view=display_view,
                            cut=cut,
                            resize=fit,
                            compression=file_compression,
                            rgb_only=True,
                            data_format=oiio_color_depth,
                            frame_range=input_range,
                            image_sequence=True)

                    for movie_format in data['movie_formats']:
                        movie_ext = movie_formats[movie_format]['ext']
                        movie_codec = movie_formats[movie_format]['codec']
                        movie_quality = movie_formats[
                            movie_format].get('quality')
                        movie_crf = movie_formats[movie_format].get('crf')
                        movie_bitrate = movie_formats[
                            movie_format].get('bitrate')

                        printf_input_path = output_image.replace(
                            '#' * frame_info['digits'],
                            f"%0{frame_info['digits']}d")
                        output_movie = os.path.join(
                            expanded_output_dir,
                            f'movie.{movie_codec}{movie_ext}')
                        convert_movie(
                            input_path=printf_input_path,
                            output_path=output_movie,
                            start_number=input_range[0],
                            video_codec=movie_codec,
                            video_quality=movie_quality,
                            constrained_quality=movie_crf,
                            video_bitrate=movie_bitrate)


def fill_listbox(listbox: Listbox, items: Iterable[str]):
    for i, x in enumerate(items):
        listbox.insert(listbox.size(), x)


def get_listbox_selection_values(listbox: Listbox):
    curselection = listbox.curselection()
    if curselection:
        return tuple(listbox.get(x) for x in curselection)


def set_entry(entry: Entry, value: str | Callable):
    if isinstance(value, Callable):
        value = value()
    entry.delete(0, 'end')
    entry.insert(0, value)


main = Tk()
main.title('Convert')

format_selecion_frame = Frame(main, borderwidth=1)
movie_format_selecion_frame = Frame(main, borderwidth=1)
entry_frame = Frame(main, borderwidth=1)
entry_frame.columnconfigure(0, weight=1)
action_frame = Frame(main, borderwidth=1)


def get_all_selection():
    data = {
        'resolutions': get_listbox_selection_values(resolutions_listbox),
        'file_formats': get_listbox_selection_values(file_formats_listbox),
        'color_depths': get_listbox_selection_values(color_depths_listbox),
        'view_transforms': get_listbox_selection_values(
            view_transforms_listbox),
        'movie_formats': get_listbox_selection_values(movie_formats_listbox)}
    return data


def set_convert_button(event):
    all_values = get_all_selection().values()
    if all(all_values):
        convert_button.config(state='normal')
    else:
        convert_button.config(state='disabled')


convert_button = Button(
    action_frame,
    text='Convert',
    command=convert)
convert_button.config(state='disabled')

resolutions_listbox = Listbox(
    format_selecion_frame, exportselection=False, selectmode='multiple')
resolutions_listbox.bind('<<ListboxSelect>>', set_convert_button)
file_formats_listbox = Listbox(
    format_selecion_frame, exportselection=False, selectmode='multiple')
file_formats_listbox.bind('<<ListboxSelect>>', set_convert_button)
color_depths_listbox = Listbox(
    format_selecion_frame, exportselection=False, selectmode='multiple')
color_depths_listbox.bind('<<ListboxSelect>>', set_convert_button)
view_transforms_listbox = Listbox(
    format_selecion_frame, exportselection=False, selectmode='multiple')
view_transforms_listbox.bind('<<ListboxSelect>>', set_convert_button)
movie_formats_listbox = Listbox(
    movie_format_selecion_frame, exportselection=False, selectmode='multiple')
input_entry = Entry(entry_frame)
input_colorspace_variable = StringVar(main)
input_colorspace_variable.set(input_colorspaces[0])
input_colorspace_choice = OptionMenu(
    entry_frame, input_colorspace_variable, *input_colorspaces)
output_entry = Entry(entry_frame)
input_dialog_button = Button(
    entry_frame,
    text='File Input',
    command=partial(set_entry, entry=input_entry, value=askopenfilename))
output_dialog_button = Button(
    entry_frame,
    text='Output Directory',
    command=partial(set_entry, entry=output_entry, value=askdirectory))

fill_listbox(resolutions_listbox, resolutions)
fill_listbox(file_formats_listbox, file_formats)
fill_listbox(color_depths_listbox, color_depths)
fill_listbox(view_transforms_listbox, view_transforms)
fill_listbox(movie_formats_listbox, movie_formats)

format_selecion_frame.pack(fill='both', expand=True)
movie_format_selecion_frame.pack(fill='both', expand=True)
entry_frame.pack(fill='both')
action_frame.pack(fill='both')
resolutions_listbox.pack(side='left', fill='both', expand=True)
file_formats_listbox.pack(side='left', fill='both', expand=True)
color_depths_listbox.pack(side='left', fill='both', expand=True)
view_transforms_listbox.pack(side='left', fill='both', expand=True)
movie_formats_listbox.pack(side='left', fill='both', expand=True)
input_entry.grid(row=0, column=0, sticky='news')
input_colorspace_choice.grid(row=0, column=1, sticky='news')
input_dialog_button.grid(row=0, column=2, sticky='news')
output_entry.grid(row=1, column=0, columnspan=2, sticky='news')
output_dialog_button.grid(row=1, column=2, sticky='news')
convert_button.pack()


if __name__ == '__main__':
    set_entry(entry=input_entry, value='$HOME/input/image.####.exr')
    set_entry(entry=output_entry, value='$HOME/output/{resolution}/{file_format}/{color_depth}/{view_transform}')
    main.mainloop()
