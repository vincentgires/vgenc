from subprocess import run


def generate_vertical_sliced_image(
        inputs: list,
        output: str,
        width: int,
        height: int) -> None:
    img_width = width / len(inputs)
    command = ['magick', 'montage']
    command.extend(inputs)
    command.extend([
        '-colorspace', 'rgb',
        '-resize', 'x{h}'.format(h=height),
        '-crop', '{w}x{h}+0+0'.format(w=img_width, h=height),
        '-mode', 'concatenate',
        '-tile', 'x1',
        '-colorspace', 'srgb',
        output])
    run(command)
