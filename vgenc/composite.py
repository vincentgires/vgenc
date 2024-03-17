from typing import Optional, Iterator
import bpy


def composite_images(
        layers_data: list[dict],
        output_path: Optional[str] = None,
        resolution: tuple[int, int] = (2048, 1080),
        frame_rate: int = 24,
        frame_range: tuple[int, int] = (1, 1),
        color_convert: Optional[tuple[str, str]] = None,
        look: Optional[str] = None,
        display_view: Optional[tuple[str, str]] = None,
        file_format: Optional[str] = None,
        color_mode: Optional[str] = None,
        color_depth: Optional[int] = None,
        compression: Optional[int] = None,
        quality: Optional[int] = None,
        codec: Optional[str] = None,
        _keep_data: bool = False,
        _render: bool = True
        ) -> None:
    """Composite images from a list of files

    Keyword arguments:
        layers_data -- list of dict with composite data
            keys:
                path -- input path
                input_colorspace -- input transform
                blend_type -- blend mode or alpha over
                split_channels -- split rgb channels into individual components
                    to apply color correction
            example:
                [{'path': '/bg.exr',
                  'input_colorspace': 'sRGB - Display'},
                 {'path': '/fg.exr',
                  'input_colorspace': 'ACEScg',
                  'blend_type': 'alpha_over'},
                 {'path': '/volume.exr',
                  'input_colorspace': 'ACEScg',
                  'blend_type': 'add',
                  'split_channels': [
                      (1.0, 1.0, 1.0), (1.0, 1.0, 1.0), (1.0, 1.0, 1.0)]}]
        output_path -- path with # to define padding of frame numbers
        color_convert -- ocio color conversion applied before look and view
        look -- ocio look name
        display_view -- ocio device display and view transform names
    """

    def next_socket(
            elements: Iterator[bpy.types.NodeSocket],
            name: str) -> bpy.types.NodeSocket:
        return next((x for x in inputs_iter if x.name == name), None)

    def split_rgb(
            scene: bpy.types.Scene,
            node: bpy.types.Node,
            multiply: list[tuple[float, float, float]]) -> bpy.types.Node:
        """
        Keyword arguments:
            node -- start node
            multiply -- color channel multiplier
                [(1.0, 1.0, 1.0), (1.0, 1.0, 1.0), (1.0, 1.0, 1.0)]
        """
        tree = scene.node_tree
        sep_node = tree.nodes.new('CompositorNodeSeparateColor')
        mix_rg_node = tree.nodes.new('CompositorNodeMixRGB')
        mix_rg_node.blend_type = 'ADD'
        mix_gb_node = tree.nodes.new('CompositorNodeMixRGB')
        mix_gb_node.blend_type = 'ADD'
        mult_r_node = tree.nodes.new('CompositorNodeMixRGB')
        mult_r_node.blend_type = 'MULTIPLY'
        mult_r_node.inputs[2].default_value = multiply[0] + (1,)
        mult_g_node = tree.nodes.new('CompositorNodeMixRGB')
        mult_g_node.blend_type = 'MULTIPLY'
        mult_g_node.inputs[2].default_value = multiply[1] + (1,)
        mult_b_node = tree.nodes.new('CompositorNodeMixRGB')
        mult_b_node.blend_type = 'MULTIPLY'
        mult_b_node.inputs[2].default_value = multiply[2] + (1,)
        set_alpha_node = tree.nodes.new('CompositorNodeSetAlpha')
        set_alpha_node.mode = 'REPLACE_ALPHA'
        tree.links.new(node.outputs[0], sep_node.inputs['Image'])
        tree.links.new(sep_node.outputs['Red'], mult_r_node.inputs[1])
        tree.links.new(mult_r_node.outputs['Image'], mix_rg_node.inputs[1])
        tree.links.new(sep_node.outputs['Green'], mult_g_node.inputs[1])
        tree.links.new(mult_g_node.outputs['Image'], mix_rg_node.inputs[2])
        tree.links.new(mix_rg_node.outputs['Image'], mix_gb_node.inputs[1])
        tree.links.new(sep_node.outputs['Blue'], mult_b_node.inputs[1])
        tree.links.new(mult_b_node.outputs['Image'], mix_gb_node.inputs[2])
        tree.links.new(mix_gb_node.outputs['Image'], set_alpha_node.inputs[0])
        tree.links.new(sep_node.outputs['Alpha'], set_alpha_node.inputs[1])
        return set_alpha_node

    # Create scene and settings
    data = bpy.data
    scene = data.scenes.new('Scene')
    if display_view is not None:
        display, view = display_view
        scene.display_settings.display_device = display
        scene.view_settings.view_transform = view
    x, y = resolution
    scene.render.resolution_x = x
    scene.render.resolution_y = y
    scene.render.fps = frame_rate
    start_frame, end_frame = frame_range
    scene.frame_start = start_frame
    scene.frame_end = end_frame

    # Set node tree and clear default nodes
    scene.use_nodes = True
    node_tree = scene.node_tree
    [node_tree.nodes.remove(node) for node in node_tree.nodes]

    # Create composite tree
    created_images = []  # Keep track of created images to remove them later
    merged_nodes = []  # Used to connect the mix node of the next layer
    for layer_data in layers_data:
        image_node = node_tree.nodes.new('CompositorNodeImage')
        image_node.frame_duration = end_frame
        if layer_path := layer_data.get('path'):
            image = data.images.load(layer_path)
            image.source = 'SEQUENCE'
            created_images.append(image)
            if input_colorspace := layer_data.get('input_colorspace'):
                image.colorspace_settings.name = input_colorspace
            image_node.image = image
        scale_node = node_tree.nodes.new('CompositorNodeScale')
        scale_node.space = 'RENDER_SIZE'
        scale_node.frame_method = 'FIT'
        node_tree.links.new(image_node.outputs[0], scale_node.inputs[0])

        node_to_merge = scale_node

        # Split channels
        if split_channels := layer_data.get('split_channels'):
            node_to_merge = split_rgb(
                scene=scene, node=scale_node, multiply=split_channels)

        # Link with previous layer
        mix_node = None
        if merged_nodes:
            blend_type = layer_data.get('blend_type')
            if blend_type == 'alpha_over':
                mix_node = node_tree.nodes.new('CompositorNodeAlphaOver')
            else:
                mix_node = node_tree.nodes.new('CompositorNodeMixRGB')
                if blend_type is not None:
                    mix_node.blend_type = blend_type.upper()
            inputs_iter = iter(mix_node.inputs)
            image_input_1 = next_socket(inputs_iter, 'Image')
            image_input_2 = next_socket(inputs_iter, 'Image')
            node_tree.links.new(merged_nodes[-1].outputs[0], image_input_1)
            node_tree.links.new(node_to_merge.outputs[0], image_input_2)

        merged_nodes.extend((image_node, node_to_merge))
        if mix_node is not None:
            merged_nodes.append(mix_node)

    if color_convert is not None:
        colorspace_node = node_tree.nodes.new(
            'CompositorNodeConvertColorSpace')
        colorspace_node.from_color_space = color_convert[0]
        colorspace_node.to_color_space = color_convert[1]
        node_tree.links.new(
            merged_nodes[-1].outputs[0], colorspace_node.inputs[0])
        merged_nodes.append(colorspace_node)

    output_node = node_tree.nodes.new('CompositorNodeComposite')
    node_tree.links.new(merged_nodes[-1].outputs[0], output_node.inputs[0])

    # Image settings
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
        match file_format:
            case 'JPEG2000':
                codec_attribute = 'jpeg2k_codec'
            case 'OPEN_EXR' | 'OPEN_EXR_MULTILAYER':
                codec_attribute = 'exr_codec'
            case 'TIFF':
                codec_attribute = 'tiff_codec'
        setattr(image_settings, codec_attribute, codec.upper())

    # Render
    if output_path is not None:
        scene.render.filepath = output_path
    if _render:
        bpy.ops.render.render(animation=True, scene=scene.name)

    # Delete scene and images
    if not _keep_data:
        data.scenes.remove(scene)
        for image in created_images:
            data.images.remove(image)


if __name__ == '__main__':
    layers_data = [
        {}, {'blend_type': 'alpha_over'},
        {'blend_type': 'add',
         'split_channels': [(.1, .2, .3), (.4, .5, .6), (.7, .8, .9)]}]
    composite_images(
        layers_data,
        frame_range=(101, 105),
        color_convert=('ACEScg', 'ACES2065-1'),
        _keep_data=True,
        _render=False)
