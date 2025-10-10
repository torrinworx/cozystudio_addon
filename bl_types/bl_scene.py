import bpy
from pathlib import Path

# from deepdiff import DeepDiff, Delta
from .replication.protocol import ReplicatedDatablock

from .utils import flush_history, get_preferences
from .bl_action import (
    dump_animation_data,
    load_animation_data,
    resolve_animation_dependencies,
)
from .bl_collection import (
    dump_collection_children,
    dump_collection_objects,
    load_collection_childrens,
    load_collection_objects,
    resolve_collection_dependencies,
)
from .bl_datablock import resolve_datablock_from_uuid
from .bl_file import get_filepath
from .dump_anything import Dumper, Loader

RENDER_SETTINGS = [
    'dither_intensity',
    'engine',
    'film_transparent',
    'filter_size',
    'fps',
    'fps_base',
    'frame_map_new',
    'frame_map_old',
    'hair_subdiv',
    'hair_type',
    'line_thickness',
    'line_thickness_mode',
    'metadata_input',
    'motion_blur_shutter',
    'pixel_aspect_x',
    'pixel_aspect_y',
    'preview_pixel_size',
    'preview_start_resolution',
    'resolution_percentage',
    'resolution_x',
    'resolution_y',
    'sequencer_gl_preview',
    'use_bake_clear',
    'use_bake_lores_mesh',
    'use_bake_multires',
    'use_bake_selected_to_active',
    'use_bake_user_scale',
    'use_border',
    'use_compositing',
    'use_crop_to_border',
    'use_file_extension',
    'use_freestyle',
    'use_full_sample',
    'use_high_quality_normals',
    'use_lock_interface',
    'use_motion_blur',
    'use_multiview',
    'use_sequencer',
    'use_sequencer_override_scene_strip',
    'use_single_layer',
    'views_format',
]

EVEE_SETTINGS = [
    'gi_diffuse_bounces',
    'gi_cubemap_resolution',
    'gi_visibility_resolution',
    'gi_irradiance_smoothing',
    'gi_glossy_clamp',
    'gi_filter_quality',
    'gi_show_irradiance',
    'gi_show_cubemaps',
    'gi_irradiance_display_size',
    'gi_cubemap_display_size',
    'gi_auto_bake',
    'taa_samples',
    'taa_render_samples',
    'use_taa_reprojection',
    'sss_samples',
    'sss_jitter_threshold',
    'use_ssr',
    'use_ssr_refraction',
    'use_ssr_halfres',
    'ssr_quality',
    'ssr_max_roughness',
    'ssr_thickness',
    'ssr_border_fade',
    'ssr_firefly_fac',
    'volumetric_start',
    'volumetric_end',
    'volumetric_tile_size',
    'volumetric_samples',
    'volumetric_sample_distribution',
    'use_volumetric_lights',
    'volumetric_light_clamp',
    'use_volumetric_shadows',
    'volumetric_shadow_samples',
    'use_gtao',
    'use_gtao_bent_normals',
    'use_gtao_bounce',
    'gtao_factor',
    'gtao_quality',
    'gtao_distance',
    'bokeh_max_size',
    'bokeh_threshold',
    'use_bloom',
    'bloom_threshold',
    'bloom_color',
    'bloom_knee',
    'bloom_radius',
    'bloom_clamp',
    'bloom_intensity',
    'use_motion_blur',
    'motion_blur_shutter',
    'motion_blur_depth_scale',
    'motion_blur_max',
    'motion_blur_steps',
    'shadow_cube_size',
    'shadow_cascade_size',
    'use_shadow_high_bitdepth',
    'gi_diffuse_bounces',
    'gi_cubemap_resolution',
    'gi_visibility_resolution',
    'gi_irradiance_smoothing',
    'gi_glossy_clamp',
    'gi_filter_quality',
    'gi_show_irradiance',
    'gi_show_cubemaps',
    'gi_irradiance_display_size',
    'gi_cubemap_display_size',
    'gi_auto_bake',
    'taa_samples',
    'taa_render_samples',
    'use_taa_reprojection',
    'sss_samples',
    'sss_jitter_threshold',
    'use_ssr',
    'use_ssr_refraction',
    'use_ssr_halfres',
    'ssr_quality',
    'ssr_max_roughness',
    'ssr_thickness',
    'ssr_border_fade',
    'ssr_firefly_fac',
    'volumetric_start',
    'volumetric_end',
    'volumetric_tile_size',
    'volumetric_samples',
    'volumetric_sample_distribution',
    'use_volumetric_lights',
    'volumetric_light_clamp',
    'use_volumetric_shadows',
    'volumetric_shadow_samples',
    'use_gtao',
    'use_gtao_bent_normals',
    'use_gtao_bounce',
    'gtao_factor',
    'gtao_quality',
    'gtao_distance',
    'bokeh_max_size',
    'bokeh_threshold',
    'use_bloom',
    'bloom_threshold',
    'bloom_color',
    'bloom_knee',
    'bloom_radius',
    'bloom_clamp',
    'bloom_intensity',
    'use_motion_blur',
    'motion_blur_shutter',
    'motion_blur_depth_scale',
    'motion_blur_max',
    'motion_blur_steps',
    'shadow_cube_size',
    'shadow_cascade_size',
    'use_shadow_high_bitdepth',
]

CYCLES_SETTINGS = [
    'shading_system',
    'progressive',
    'use_denoising',
    'denoiser',
    'use_square_samples',
    'samples',
    'aa_samples',
    'diffuse_samples',
    'glossy_samples',
    'transmission_samples',
    'ao_samples',
    'mesh_light_samples',
    'subsurface_samples',
    'volume_samples',
    'sampling_pattern',
    'use_layer_samples',
    'sample_all_lights_direct',
    'sample_all_lights_indirect',
    'light_sampling_threshold',
    'use_adaptive_sampling',
    'adaptive_threshold',
    'adaptive_min_samples',
    'min_light_bounces',
    'min_transparent_bounces',
    'caustics_reflective',
    'caustics_refractive',
    'blur_glossy',
    'max_bounces',
    'diffuse_bounces',
    'glossy_bounces',
    'transmission_bounces',
    'volume_bounces',
    'transparent_max_bounces',
    'volume_step_rate',
    'volume_max_steps',
    'dicing_rate',
    'max_subdivisions',
    'dicing_camera',
    'offscreen_dicing_scale',
    'film_exposure',
    'film_transparent_glass',
    'film_transparent_roughness',
    'filter_type',
    'pixel_filter_type',
    'filter_width',
    'seed',
    'use_animated_seed',
    'sample_clamp_direct',
    'sample_clamp_indirect',
    'tile_order',
    'use_progressive_refine',
    'bake_type',
    'use_camera_cull',
    'camera_cull_margin',
    'use_distance_cull',
    'distance_cull_margin',
    'motion_blur_position',
    'rolling_shutter_type',
    'rolling_shutter_duration',
    'texture_limit',
    'texture_limit_render',
    'ao_bounces',
    'ao_bounces_render',
]

VIEW_SETTINGS = [
    'look',
    'view_transform',
    'exposure',
    'gamma',
    'use_curve_mapping',
    'white_level',
    'black_level'
]


def dump_sequence(sequence) -> dict:
    """ Dump a sequence to a dict

        :arg sequence: sequence to dump
        :type sequence: bpy.types.Sequence
        :return dict:
    """
    dumper = Dumper()
    dumper.exclude_filter = [
        'lock',
        'select',
        'select_left_handle',
        'select_right_handle',
        'strobe'
    ]
    dumper.depth = 1
    data = dumper.dump(sequence)

    # TODO: Support multiple images
    if sequence.type == 'IMAGE':
        data['filenames'] = [e.filename for e in sequence.elements]

    # Effect strip inputs
    input_count = getattr(sequence, 'input_count', None)
    if input_count:
        for n in range(input_count):
            input_name = f"input_{n+1}"
            data[input_name] = getattr(sequence, input_name).name

    return data


def load_sequence(sequence_data: dict,
                  sequence_editor: bpy.types.SequenceEditor):
    """ Load sequence from dumped data

        :arg sequence_data: sequence to dump
        :type sequence_data:dict
        :arg sequence_editor: root sequence editor
        :type sequence_editor: bpy.types.SequenceEditor
    """
    strip_type = sequence_data.get('type')
    strip_name = sequence_data.get('name')
    strip_channel = sequence_data.get('channel')
    strip_frame_start = sequence_data.get('frame_start')

    sequence = sequence_editor.sequences_all.get(strip_name, None)

    if sequence is None:
        if strip_type == 'SCENE':
            strip_scene = bpy.data.scenes.get(sequence_data.get('scene'))
            sequence = sequence_editor.sequences.new_scene(strip_name,
                                                           strip_scene,
                                                           strip_channel,
                                                           strip_frame_start)
        elif strip_type == 'MOVIE':
            filepath = get_filepath(Path(sequence_data['filepath']).name)
            sequence = sequence_editor.sequences.new_movie(strip_name,
                                                           filepath,
                                                           strip_channel,
                                                           strip_frame_start)
        elif strip_type == 'SOUND':
            filepath = bpy.data.sounds[sequence_data['sound']].filepath
            sequence = sequence_editor.sequences.new_sound(strip_name,
                                                           filepath,
                                                           strip_channel,
                                                           strip_frame_start)
        elif strip_type == 'IMAGE':
            images_name = sequence_data.get('filenames')
            filepath = get_filepath(images_name[0])
            sequence = sequence_editor.sequences.new_image(strip_name,
                                                           filepath,
                                                           strip_channel,
                                                           strip_frame_start)
            # load other images
            if len(images_name) > 1:
                for img_idx in range(1, len(images_name)):
                    sequence.elements.append((images_name[img_idx]))
        else:
            seq = {}

            for i in range(sequence_data['input_count']):
                seq[f"seq{i+1}"] = sequence_editor.sequences_all.get(
                    sequence_data.get(f"input_{i+1}", None))

            sequence = sequence_editor.sequences.new_effect(name=strip_name,
                                                            type=strip_type,
                                                            channel=strip_channel,
                                                            frame_start=strip_frame_start,
                                                            frame_end=sequence_data['frame_final_end'],
                                                            **seq)

    loader = Loader()

    loader.exclure_filter = ['filepath', 'sound', 'filenames', 'fps']
    loader.load(sequence, sequence_data)
    sequence.select = False


class BlScene(ReplicatedDatablock):
    is_root = True
    use_delta = True

    bl_id = "scenes"
    bl_class = bpy.types.Scene
    bl_check_common = True
    bl_icon = 'SCENE_DATA'
    bl_reload_parent = False

    @staticmethod
    def construct(data: dict) -> object:
        return bpy.data.scenes.new(data["name"])

    @staticmethod
    def load(data: dict, datablock: object):
        load_animation_data(data.get('animation_data'), datablock)

        # Load other meshes metadata
        loader = Loader()
        loader.load(datablock, data)

        # Load master collection
        load_collection_objects(
            data['collection']['objects'], datablock.collection)
        load_collection_childrens(
            data['collection']['children'], datablock.collection)

        if 'world' in data.keys():
            datablock.world = bpy.data.worlds[data['world']]

        # Annotation
        gpencil_uid = data.get('grease_pencil')
        if gpencil_uid:
            datablock.grease_pencil = resolve_datablock_from_uuid(gpencil_uid, bpy.data.grease_pencils)
        prefs = get_preferences()
        if prefs and prefs.sync_flags.sync_render_settings:
            if 'eevee' in data.keys():
                loader.load(datablock.eevee, data['eevee'])

            if 'cycles' in data.keys():
                loader.load(datablock.cycles, data['cycles'])

            if 'render' in data.keys():
                loader.load(datablock.render, data['render'])

            view_settings = data.get('view_settings')
            if view_settings:
                loader.load(datablock.view_settings, view_settings)
                if datablock.view_settings.use_curve_mapping and \
                        'curve_mapping' in view_settings:
                    # TODO: change this ugly fix
                    datablock.view_settings.curve_mapping.white_level = view_settings['curve_mapping']['white_level']
                    datablock.view_settings.curve_mapping.black_level = view_settings['curve_mapping']['black_level']
                    datablock.view_settings.curve_mapping.update()

        # Sequencer
        sequences = data.get('sequences')

        if sequences:
            # Create sequencer data
            datablock.sequence_editor_create()
            vse = datablock.sequence_editor

            # Clear removed sequences
            for seq in vse.sequences_all:
                if seq.name not in sequences:
                    vse.sequences.remove(seq)
            # Load existing sequences
            for seq_data in sequences.values():
                load_sequence(seq_data, vse)
        # If the sequence is no longer used, clear it
        elif datablock.sequence_editor and not sequences:
            datablock.sequence_editor_clear()

        # Timeline markers
        markers = data.get('timeline_markers')
        if markers:
            datablock.timeline_markers.clear()
            for name, frame, camera in markers:
                marker = datablock.timeline_markers.new(name, frame=frame)
                if camera:
                    marker.camera = resolve_datablock_from_uuid(camera, bpy.data.objects)
                marker.select = False
        # FIXME: Find a better way after the replication big refacotoring
        # Keep other user from deleting collection object by flushing their history
        flush_history()

    @staticmethod
    def dump(datablock: object) -> dict:
        data = {}
        data['animation_data'] = dump_animation_data(datablock)

        # Metadata
        scene_dumper = Dumper()
        scene_dumper.depth = 1
        scene_dumper.include_filter = [
            'name',
            'world',
            'id',
            'frame_start',
            'frame_end',
            'frame_step',
        ]
        prefs = get_preferences()
        if prefs and prefs.sync_flags.sync_active_camera:
            scene_dumper.include_filter.append('camera')

        data.update(scene_dumper.dump(datablock))

        # Master collection
        data['collection'] = {}
        data['collection']['children'] = dump_collection_children(
            datablock.collection)
        data['collection']['objects'] = dump_collection_objects(
            datablock.collection)

        scene_dumper.depth = 1
        scene_dumper.include_filter = None

        # Render settings
        if prefs and prefs.sync_flags.sync_render_settings:
            scene_dumper.include_filter = RENDER_SETTINGS

            data['render'] = scene_dumper.dump(datablock.render)

            if datablock.render.engine == 'BLENDER_EEVEE':
                scene_dumper.include_filter = EVEE_SETTINGS
                data['eevee'] = scene_dumper.dump(datablock.eevee)
            elif datablock.render.engine == 'CYCLES':
                scene_dumper.include_filter = CYCLES_SETTINGS
                data['cycles'] = scene_dumper.dump(datablock.cycles)

            scene_dumper.include_filter = VIEW_SETTINGS
            data['view_settings'] = scene_dumper.dump(datablock.view_settings)

            if datablock.view_settings.use_curve_mapping:
                data['view_settings']['curve_mapping'] = scene_dumper.dump(
                    datablock.view_settings.curve_mapping)
                scene_dumper.depth = 5
                scene_dumper.include_filter = [
                    'curves',
                    'points',
                    'location',
                ]
                data['view_settings']['curve_mapping']['curves'] = scene_dumper.dump(
                    datablock.view_settings.curve_mapping.curves)

        # Sequence
        vse = datablock.sequence_editor
        if vse:
            dumped_sequences = {}
            for seq in vse.sequences_all:
                dumped_sequences[seq.name] = dump_sequence(seq)
            data['sequences'] = dumped_sequences

        # Timeline markers
        if datablock.timeline_markers:
            data['timeline_markers'] = [(m.name, m.frame, getattr(m.camera, 'uuid', None)) for m in datablock.timeline_markers]

        if datablock.grease_pencil:
            data['grease_pencil'] = datablock.grease_pencil.uuid

        return data

    @staticmethod
    def resolve_deps(datablock: object) -> list[object]:
        deps = []

        # Master Collection
        deps.extend(resolve_collection_dependencies(datablock.collection))

        # world
        if datablock.world:
            deps.append(datablock.world)

        # annotations
        if datablock.grease_pencil:
            deps.append(datablock.grease_pencil)

        deps.extend(resolve_animation_dependencies(datablock))

        # Sequences
        vse = datablock.sequence_editor
        if vse:
            for sequence in vse.sequences_all:
                if sequence.type == 'MOVIE' and sequence.filepath:
                    deps.append(Path(bpy.path.abspath(sequence.filepath)))
                elif sequence.type == 'SOUND' and sequence.sound:
                    deps.append(sequence.sound)
                elif sequence.type == 'IMAGE':
                    for elem in sequence.elements:
                        sequence.append(
                            Path(bpy.path.abspath(sequence.directory), elem.filename)
                        )

        return deps

    @staticmethod
    def resolve(data: dict) -> object:
        uuid = data.get('uuid')
        name = data.get('name')
        datablock = resolve_datablock_from_uuid(uuid, bpy.data.scenes)
        if datablock is None:
            datablock = bpy.data.scenes.get(name)

        return datablock

    # @staticmethod
    # def compute_delta(last_data: dict, current_data: dict) -> Delta:
    #     exclude_path = []

    #     if not get_preferences().sync_flags.sync_render_settings:
    #         exclude_path.append("root['eevee']")
    #         exclude_path.append("root['cycles']")
    #         exclude_path.append("root['view_settings']")
    #         exclude_path.append("root['render']")

    #     if not get_preferences().sync_flags.sync_active_camera:
    #         exclude_path.append("root['camera']")

    #     diff_params = {
    #         'exclude_paths': exclude_path,
    #         'ignore_order': True,
    #         'report_repetition': True
    #     }
    #     delta_params = {
    #         # 'mutate': True
    #     }

    #     return Delta(
    #         DeepDiff(last_data,
    #                  current_data,
    #                  cache_size=5000,
    #                  **diff_params),
    #         **delta_params)


_type = bpy.types.Scene
_class = BlScene
