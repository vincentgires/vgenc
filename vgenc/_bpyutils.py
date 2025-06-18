import os
import sys
import bpy


def convert_os_path(path):
    if sys.platform.startswith('linux'):
        if path.startswith(r'\\'):
            path = '/' + path.replace('\\', '/')[2:]
    elif sys.platform.startswith('win'):
        if path.startswith('/') and not path.startswith('//'):
            path = r'\\' + os.path.normpath(path)[1:]
    return path


def normpath(path):
    # Remove double slash to be able to use for absolute path
    if sys.platform.startswith('linux'):
        path = path.replace('//', '/')
    # Result: /my/path
    # Make linux path compatible with windows
    elif sys.platform.startswith('win'):
        if path.startswith('/') and not path.startswith('//'):
            path = '/{}'.format(path)
    # Result after normpath: \\my\path
    path = os.path.normpath(path)
    return path


def set_render_settings(
        scene: bpy.types.Scene,
        look: str | None = None,
        display_view: tuple[str, str] | None = None,
        file_format: str | None = None,
        color_mode: str | None = None,
        color_depth: int | None = None,
        compression: int | None = None,
        quality: int | None = None,
        codec: str | None = None,
        additional_image_settings: dict | None = None,
        resolution: tuple[int, int] | None = None):
    codec_attributes = {
        'JPEG2000': 'jpeg2k_codec',
        'OPEN_EXR': 'exr_codec',
        'OPEN_EXR_MULTILAYER': 'exr_codec',
        'TIFF': 'tiff_codec'}
    if look is not None:
        scene.view_settings.look = look
    if display_view is not None:
        display, view = display_view
        scene.display_settings.display_device = display
        scene.view_settings.view_transform = view
    image_settings = scene.render.image_settings
    if file_format is not None:
        image_settings.file_format = file_format.upper()
    if color_mode is not None:
        image_settings.color_mode = color_mode.upper()
    if color_depth is not None:
        image_settings.color_depth = str(color_depth)
    if compression is not None:
        image_settings.compression = compression
    if quality is not None:
        image_settings.quality = quality
    if codec is not None:
        if codec_attribute := codec_attributes.get(
                image_settings.file_format):
            setattr(image_settings, codec_attribute, codec.upper())
    if additional_image_settings is not None:
        for k, v in additional_image_settings.items():
            setattr(image_settings, k, v)
    if resolution is not None:
        x, y = resolution
        scene.render.resolution_x = x
        scene.render.resolution_y = y
        scene.render.resolution_percentage = 100


def set_scene_resolution_from_image_strip(
        scene: bpy.types.Scene,
        strip: bpy.types.TextStrip):
    if strip.type != 'IMAGE':
        return
    first_elem = strip.elements[0]
    image_path = os.path.join(strip.directory, first_elem.filename)
    # Temporarily load the image to read its dimensions
    # strip.elements[0].orig_width and orig_height can return 0 if strip
    # hasn't been display once.
    img = bpy.data.images.load(image_path)
    scene.render.resolution_x = img.size[0]
    scene.render.resolution_y = img.size[1]
    bpy.data.images.remove(img)  # Remove after usage


def load_image_sequence_strip(
        scene: bpy.types.Scene,
        directory: str,
        images: list[str],
        frame_range: tuple[int, int],
        channel: int = 1,
        colorspace=None,
        set_scene_resolution=False):
    if not scene.sequence_editor:
        scene.sequence_editor_create()
    sequences = scene.sequence_editor.sequences
    first_frame = images[0]
    start, end = frame_range
    strip = sequences.new_image(
        name=first_frame,
        filepath=normpath(os.path.join(directory, first_frame)),
        channel=channel,
        frame_start=int(start))
    for image in images[1:]:
        strip.elements.append(image)
    strip.select = False
    if colorspace is not None:
        strip.colorspace_settings.name = colorspace
    if set_scene_resolution:
        set_scene_resolution_from_image_strip(scene, strip)
    scene.frame_start = start
    scene.frame_end = end
    return strip


def create_text_strip(
        scene: bpy.types.Scene,
        text: str,
        frame_range: tuple[int, int],
        channel: int = 2,
        location: tuple[float, float] = (0.0, 1.0),
        font_size: int = 100,
        color: tuple = (1.0, 1.0, 1.0, 1.0),
        font: bpy.types.VectorFont | None = None,
        anchor_x: str = 'LEFT',
        anchor_y: str = 'TOP',
        name: str = 'Text'):
    if not scene.sequence_editor:
        scene.sequence_editor_create()
    start, end = frame_range
    strip = scene.sequence_editor.sequences.new_effect(
        name=name,
        type='TEXT',
        channel=channel,
        frame_start=start,
        frame_end=end)
    strip.text = text
    strip.location = location
    strip.font_size = font_size
    strip.color = color
    if font is not None:
        strip.font = font
    strip.anchor_x = anchor_x
    strip.anchor_y = anchor_y
    return strip


def _expand_text_ranges(
        text_ranges: list[tuple[int, int, str]]) -> list[tuple[int, int, str]]:
    """Expand '{frame}' in text ranges"""
    result = []
    for start, end, text in text_ranges:
        if '{frame}' in text:
            for frame in range(start, end):
                result.append((frame, frame + 1, text.format(frame=frame)))
        else:
            result.append((start, end, text))
    return result


def create_text_strips_by_ranges(
        scene: bpy.types.Scene,
        text_ranges: list[tuple[int, int, str]],
        channel: int = 2,
        location: tuple[float, float] = (0.0, 1.0),
        font_size: int = 100,
        color: tuple = (1.0, 1.0, 1.0, 1.0),
        font: bpy.types.VectorFont | None = None,
        anchor_x: str = 'LEFT',
        anchor_y: str = 'TOP'):
    """
    Args:
        text_ranges: list of tuples (start_frame, end_frame, text)
    """
    strips = []
    text_ranges = _expand_text_ranges(text_ranges)
    for i, (start, end, text) in enumerate(text_ranges):
        strip = create_text_strip(
            scene=scene,
            text=text,
            frame_range=(start, end),
            channel=channel,
            location=location,
            font_size=font_size,
            color=color,
            font=font,
            anchor_x=anchor_x,
            anchor_y=anchor_y,
            name=f'Text{i}')
        strips.append(strip)
    return strips


if __name__ == '__main__':
    create_text_strips_by_ranges(
        bpy.context.scene,
        text_ranges=[(1, 10, 'test'), (10, 11, 'test1'), (11, 12, 'test3')])
