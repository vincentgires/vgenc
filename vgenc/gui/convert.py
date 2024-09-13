# TODO: stereo anaglyph movie
# TODO: add ocio looks
# TODO: read ocio config for listing colorspaces, view transforms and looks
# TODO: image preview

import os
import re
from tkinter import (
    Tk, Listbox, Entry, Button, Frame, LabelFrame, StringVar, IntVar,
    OptionMenu, Checkbutton)
from tkinter.filedialog import askopenfilename, askdirectory
from functools import partial
from typing import Callable, Iterable
from ..convert import convert_movie
from ..files import get_frame_info, find_image_sequence_range
from ..probe import get_image_size
from ..batch import batch_convert_image

input_colorspaces = [
    'ACES2065-1',
    'ACEScg',
    'Linear sRGB',
    'sRGB - Texture']
resolutions = {
    '2k Full': {
        'cut': (2048, 1080)},
    '2k Univisium': {
        'cut': (2048, 1024)},
    '2k Scope': {
        'cut': (2048, 858)},
    '2k Flat': {
        'cut': (1998, 1080)},
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
        'color_depths': ['8 bits', '16 bits integer']}}
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

_oiiotool_bit_depths = {
    (8,): 'uint8',
    (10,): 'uint10',
    (12,): 'uint12',
    (16, 'integer'): 'uint16',
    (16, 'float'): 'half',
    (32, 'float'): 'float'}

batch_selection: list[dict] = []


def find_views_paths(path: str) -> list[tuple[int, int]] | None:
    # Find %v{name1|name2|etc}
    pattern = r'%v\{([^}]+)\}'
    if matches := re.findall(pattern, path):
        views = set([x for match in matches for x in match.split('|')])
        return [(view, re.sub(pattern, view, path)) for view in views]


def convert(
        exec_image_convert: Callable = batch_convert_image,
        exec_movie_convert: Callable = convert_movie):
    input_path = os.path.expandvars(input_entry.get())
    output_path = os.path.expandvars(output_entry.get())

    # Multiview: extend input path with views
    view_paths = find_views_paths(input_path)
    if view_paths is None:
        view_paths = [(None, input_path)]

    for view, input_path in view_paths:
        frame_info = get_frame_info(input_path)
        if frame_info is None:
            continue
        if frame_range_variable.get():
            input_range = (
                int(frame_start_entry.get()), int(frame_end_entry.get()))
            frame_jump = int(frame_jump_entry.get())
        else:
            input_range = find_image_sequence_range(
                path=input_path,
                digits=frame_info['digits'],
                prefix=frame_info['start'],
                suffix=frame_info['end'])
            if input_range is None:
                continue
            frame_jump = 1

        first_frame_path = (
            f"{frame_info['start']}"
            f"{input_range[0]:0{frame_info['digits']}}"
            f"{frame_info['end']}")
        if not os.path.exists(first_frame_path):
            raise IOError(f'Cannot find file: {first_frame_path}')
        input_x, input_y = get_image_size(first_frame_path)

        for data in batch_selection:
            resolution = data['resolution']
            resolution_value = resolutions.get(resolution)
            file_format = data['file_format']
            file_format_value = file_formats.get(file_format)
            color_depth = data['color_depth']
            color_depth_value = color_depths.get(color_depth)
            view_transform = data['view_transform']
            view_transform_value = view_transforms.get(view_transform)
            movie_container = data['movie_container']
            movie_container_value = movie_containers.get(movie_container)
            movie_codec = data['movie_codec']
            movie_codec_value = movie_codecs.get(movie_codec)

            # Resolution
            if cut := resolution_value.get('cut'):
                cut_x, cut_y = cut
                cut_offset = (
                    int((input_x - cut_x) / 2),
                    int((input_y - cut_y) / 2))
                cut = ((cut_x, cut_y), cut_offset)
            fit = resolution_value.get('fit')

            # File format
            file_ext = file_format_value['ext']
            file_compression = file_format_value.get('compression')

            # Color depth
            oiio_color_depth = _oiiotool_bit_depths[color_depth_value]

            # View transform
            expanded_output_dir = output_path.format(
                resolution=resolution,
                file_format=file_format,
                color_depth=color_depth,
                view_transform=view_transform)
            file_name = f"image.{'#' * frame_info['digits']}{file_ext}"
            output_image = os.path.join(expanded_output_dir, file_name)
            if view is not None:
                output_image = os.path.join(
                    expanded_output_dir, view, file_name)

            exec_image_convert(
                input_path=input_path,
                output_path=output_image,
                frame_range=input_range,
                frame_jump=frame_jump,
                cut=cut,
                fit=fit,
                compression=file_compression,
                data_format=oiio_color_depth,
                color_depth=color_depth_value[0],
                input_colorspace=input_colorspace_variable.get(),
                display_view=view_transform_value)

            # Movie
            if all(x is not None for x in (movie_container, movie_codec)):
                movie_ext = movie_container_value['ext']
                movie_quality = movie_codec_value.get('quality')
                movie_crf = movie_codec_value.get('crf')
                movie_bitrate = movie_codec_value.get('bitrate')
                movie_encoder_codec = movie_codec_value.get('codec')
                movie_encoder_profile = movie_codec_value.get('profile')
                movie_encoder_pixfmt = movie_codec_value.get('pixel_format')

                # Movie encoding
                printf_input_path = output_image.replace(
                    '#' * frame_info['digits'], f"%0{frame_info['digits']}d")
                output_movie = os.path.join(
                    expanded_output_dir, f'movie.{movie_codec}{movie_ext}')
                exec_movie_convert(
                    input_path=printf_input_path,
                    output_path=output_movie,
                    start_number=input_range[0],
                    video_codec=movie_encoder_codec,
                    video_profile=movie_encoder_profile,
                    video_quality=movie_quality,
                    constrained_quality=movie_crf,
                    video_bitrate=movie_bitrate,
                    pixel_format=movie_encoder_pixfmt)

    clear_batch_selection()


def fill_listbox(listbox: Listbox, items: Iterable[str], clear: bool = False):
    if clear:
        listbox.delete(0, 'end')
    for i, x in enumerate(items):
        listbox.insert(listbox.size(), x)


def get_listbox_selection_values(listbox: Listbox, multiple=True):
    curselection = listbox.curselection()
    if curselection:
        if multiple:
            return tuple(listbox.get(x) for x in curselection)
        else:
            return listbox.get(curselection[0])


def set_listbox(listbox: Listbox, value: str | None):
    if value is None:
        return
    listbox.select_clear(0, 'end')
    all_values = listbox.get(0, 'end')
    index = all_values.index(value)
    listbox.selection_set(index)


def set_entry(entry: Entry, value: str | Callable):
    if isinstance(value, Callable):
        value = value()
    entry.delete(0, 'end')
    entry.insert(0, value)


main = Tk()
main.title('Convert')

format_selecion_frame = LabelFrame(main, borderwidth=1, text='Image')
movie_format_selecion_frame = LabelFrame(main, borderwidth=1, text='Movie')
batch_selection_frame = LabelFrame(main, borderwidth=1, text='Batch Selection')
entry_frame = LabelFrame(main, borderwidth=1, text='IO')
entry_frame.columnconfigure(0, weight=1)
frame_range_frame = Frame(main, borderwidth=1)
frame_range_frame.columnconfigure(0, weight=1)
action_frame = Frame(main, borderwidth=1)


def get_current_selection():
    data = {
        'resolution': get_listbox_selection_values(
            resolutions_listbox, multiple=False),
        'file_format': get_listbox_selection_values(
            file_formats_listbox, multiple=False),
        'color_depth': get_listbox_selection_values(
            color_depths_listbox, multiple=False),
        'view_transform': get_listbox_selection_values(
            view_transforms_listbox, multiple=False),
        'movie_container': get_listbox_selection_values(
            movie_containers_listbox, multiple=False),
        'movie_codec': get_listbox_selection_values(
            movie_codecs_listbox, multiple=False)}
    return data


def set_combinaison_validity():
    """Check validity of combinaison"""
    data_selection = get_current_selection()
    image_data_enum = [
        'resolution', 'file_format', 'color_depth', 'view_transform']
    movie_data_enum = ['movie_container', 'movie_codec']
    image_data_values = [
        v for k, v in data_selection.items() if k in image_data_enum]
    movie_data_values = [
        v for k, v in data_selection.items() if k in movie_data_enum]
    m_ok = all(movie_data_values) or all(x is None for x in movie_data_values)
    if all(image_data_values) and m_ok:
        add_to_batch_selection_button.config(state='normal')
    else:
        add_to_batch_selection_button.config(state='disabled')


def on_rightclick(event):
    # Unselect
    event.widget.selection_clear(0, 'end')

    set_combinaison_validity()


def _update_file_formats_listbox():
    selected_file_format = get_listbox_selection_values(
        file_formats_listbox, multiple=False)
    if selected_file_format is None:
        return
    available_color_depths = file_formats[selected_file_format].get(
        'color_depths', color_depths.keys())
    fill_listbox(color_depths_listbox, available_color_depths, clear=True)


def _update_movie_containers_listbox():
    selected_movie_container = get_listbox_selection_values(
        movie_containers_listbox, multiple=False)
    if selected_movie_container is None:
        return
    available_movie_codecs = movie_containers[
        selected_movie_container].get('codecs', movie_codecs.keys())
    fill_listbox(movie_codecs_listbox, available_movie_codecs, clear=True)


def on_update_selection(event):
    # Adapt color depths from file format selected
    if event.widget is file_formats_listbox:
        _update_file_formats_listbox()

    # Adapt movie codecs from movie container selected
    if event.widget is movie_containers_listbox:
        _update_movie_containers_listbox()

    set_combinaison_validity()


def on_batch_selection_doubleclick(event):
    if curselection_indexes := batch_selection_listbox.curselection():
        curindex = curselection_indexes[0]
        selection_data = batch_selection[curindex]
        set_listbox(
            resolutions_listbox,
            selection_data['resolution'])
        set_listbox(
            file_formats_listbox,
            selection_data['file_format'])
        _update_file_formats_listbox()
        set_listbox(
            color_depths_listbox,
            selection_data['color_depth'])
        set_listbox(
            view_transforms_listbox,
            selection_data['view_transform'])
        set_listbox(
            movie_containers_listbox,
            selection_data['movie_container'])
        _update_movie_containers_listbox()
        set_listbox(
            movie_codecs_listbox,
            selection_data['movie_codec'])


def add_config_to_batch_selection():
    if convert_button['state'] == 'disabled':
        convert_button['state'] = 'normal'
    selection_data = get_current_selection()
    batch_selection.append(selection_data)
    item = ' | '.join([x for x in selection_data.values() if x is not None])
    fill_listbox(batch_selection_listbox, [item])


def clear_batch_selection():
    batch_selection.clear()
    batch_selection_listbox.delete(0, 'end')


def frame_range_checkbox_command():
    for entry_widget in (frame_start_entry, frame_end_entry, frame_jump_entry):
        if entry_widget['state'] == 'normal':
            entry_widget.config(state='disabled')
        else:
            entry_widget.config(state='normal')


resolutions_listbox = Listbox(
    format_selecion_frame, exportselection=False, selectmode='browse')
resolutions_listbox.bind('<<ListboxSelect>>', on_update_selection)
resolutions_listbox.bind('<Button-3>', on_rightclick)
file_formats_listbox = Listbox(
    format_selecion_frame, exportselection=False, selectmode='browse')
file_formats_listbox.bind('<<ListboxSelect>>', on_update_selection)
file_formats_listbox.bind('<Button-3>', on_rightclick)
color_depths_listbox = Listbox(
    format_selecion_frame, exportselection=False, selectmode='browse')
color_depths_listbox.bind('<<ListboxSelect>>', on_update_selection)
color_depths_listbox.bind('<Button-3>', on_rightclick)
view_transforms_listbox = Listbox(
    format_selecion_frame, exportselection=False, selectmode='browse')
view_transforms_listbox.bind('<<ListboxSelect>>', on_update_selection)
view_transforms_listbox.bind('<Button-3>', on_rightclick)
movie_containers_listbox = Listbox(
    movie_format_selecion_frame, exportselection=False, selectmode='browse')
movie_containers_listbox.bind('<<ListboxSelect>>', on_update_selection)
movie_containers_listbox.bind('<Button-3>', on_rightclick)
movie_codecs_listbox = Listbox(
    movie_format_selecion_frame, exportselection=False, selectmode='browse')
movie_codecs_listbox.bind('<<ListboxSelect>>', on_update_selection)
movie_codecs_listbox.bind('<Button-3>', on_rightclick)
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
frame_range_variable = IntVar(main)
frame_range_checkbox = Checkbutton(
    frame_range_frame, text='Frame Range', variable=frame_range_variable,
    command=frame_range_checkbox_command)
frame_start_entry = Entry(frame_range_frame)
frame_end_entry = Entry(frame_range_frame)
frame_jump_entry = Entry(frame_range_frame)
set_entry(entry=frame_start_entry, value='1')
set_entry(entry=frame_end_entry, value='100')
set_entry(entry=frame_jump_entry, value='1')
for frwidget in (frame_start_entry, frame_end_entry, frame_jump_entry):
    frwidget.config(state='disabled')
batch_selection_listbox = Listbox(batch_selection_frame, exportselection=False)
batch_selection_listbox.bind(
    '<Double-Button-1>', on_batch_selection_doubleclick)
add_to_batch_selection_button = Button(
    batch_selection_frame,
    text='Add',
    command=add_config_to_batch_selection)
add_to_batch_selection_button.config(state='disabled')
clear_batch_selection_button = Button(
    batch_selection_frame,
    text='Clear',
    command=partial(clear_batch_selection))
convert_button = Button(
    action_frame,
    text='Convert',
    command=convert)
convert_button.config(state='disabled')

fill_listbox(resolutions_listbox, resolutions)
fill_listbox(file_formats_listbox, file_formats)
fill_listbox(color_depths_listbox, color_depths)
fill_listbox(view_transforms_listbox, view_transforms)
fill_listbox(movie_containers_listbox, movie_containers)
fill_listbox(movie_codecs_listbox, movie_codecs)

format_selecion_frame.pack(fill='both', expand=True)
movie_format_selecion_frame.pack(fill='both', expand=True)
batch_selection_frame.pack(fill='both', expand=True)
batch_selection_listbox.pack(fill='both', expand=True)
add_to_batch_selection_button.pack(fill='both')
clear_batch_selection_button.pack(fill='both')
entry_frame.pack(fill='both')
frame_range_frame.pack(fill='both', expand=True)
frame_range_checkbox.grid(row=0, column=0, sticky='news')
frame_start_entry.grid(row=0, column=1, sticky='news')
frame_end_entry.grid(row=0, column=2, sticky='news')
frame_jump_entry.grid(row=0, column=3, sticky='news')
action_frame.pack(fill='both')
resolutions_listbox.pack(side='left', fill='both', expand=True)
file_formats_listbox.pack(side='left', fill='both', expand=True)
color_depths_listbox.pack(side='left', fill='both', expand=True)
view_transforms_listbox.pack(side='left', fill='both', expand=True)
movie_containers_listbox.pack(side='left', fill='both', expand=True)
movie_codecs_listbox.pack(side='left', fill='both', expand=True)
input_entry.grid(row=0, column=0, sticky='news')
input_colorspace_choice.grid(row=0, column=1, sticky='news')
input_dialog_button.grid(row=0, column=2, sticky='news')
output_entry.grid(row=1, column=0, columnspan=2, sticky='news')
output_dialog_button.grid(row=1, column=2, sticky='news')
convert_button.pack(fill='both')

if __name__ == '__main__':
    set_entry(entry=input_entry, value='$HOME/input/image.####.exr')
    set_entry(entry=output_entry, value='$HOME/output/{resolution}/{file_format}/{color_depth}/{view_transform}')
    main.mainloop()
