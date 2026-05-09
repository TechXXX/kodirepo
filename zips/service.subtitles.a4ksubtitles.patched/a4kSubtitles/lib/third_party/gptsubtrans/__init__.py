import sys
import os

# Add external_libs directory to sys.path for vendored dependencies
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'external_libs'))

from PySubtitle.Options import Options
from PySubtitle.SubtitleFile import SubtitleFile
from PySubtitle.TranslationProvider import TranslationProvider

def translate(
    input_file,
    target_language,
    output_file,
    api_key=None,
    provider="OpenAI",
    model="gpt-4.1-mini-2025-04-14",
    moviename=None,
    scene_threshold=60.0,
    min_batch_size=1,
    max_batch_size=30,
    preprocess_subtitles=False,
    postprocess_translation=False,
    retry_on_error=False,
    stop_on_error=True,
    theme=None,
    break_long_lines=False,
    max_line_duration=None,
    min_line_duration=None,
    autosave=False,
    description=None,
    addrtlmarkers=False,
    includeoriginal=False,
    instructionfile=None,
    matchpartialwords=False,
    maxlines=None,
    maxsummaries=None,
    name=None,
    names=None,
    ratelimit=None,
    substitution=None,
    project=None,
    writebackup=False,
    begin_seconds=None,
    end_seconds=None,
    priority_seconds=None,
    log=print,
    partial_callback=None,
):
    # Input file check
    if not os.path.exists(input_file):
        log(f"Input file does not exist: {input_file}")
        raise FileNotFoundError(f"Input file does not exist: {input_file}")

    # Instruction file path
    if instructionfile:
        instruction_file_path = instructionfile
    else:
        instruction_file_path = os.path.join(os.path.dirname(__file__), "instructions.txt")

    # Build options
    options_dict = {
        'target_language': target_language,
        'provider': provider,
        'model': model,
        'scene_threshold': scene_threshold,
        'min_batch_size': min_batch_size,
        'max_batch_size': max_batch_size,
        'preprocess_subtitles': preprocess_subtitles,
        'postprocess_translation': postprocess_translation,
        'retry_on_error': retry_on_error,
        'stop_on_error': stop_on_error,
        'theme': theme,
        'break_long_lines': break_long_lines,
        'max_line_duration': max_line_duration,
        'min_line_duration': min_line_duration,
        'autosave': autosave,
        'movie_name': moviename or os.path.splitext(os.path.basename(input_file))[0],
        'description': description,
        'add_right_to_left_markers': addrtlmarkers,
        'include_original': includeoriginal,
        'instruction_file': instruction_file_path,
        'substitution_mode': "Partial Words" if matchpartialwords else "Auto",
        'max_lines': maxlines,
        'max_context_summaries': maxsummaries,
        'rate_limit': ratelimit,
        'project': project,
        'write_backup': writebackup,
        'api_key': api_key if api_key else None,
    }

    # Handle names and substitutions
    if names or name:
        if names:
            options_dict['names'] = [n.strip() for n in names.split(',') if n.strip()]
        elif name:
            options_dict['names'] = name

    if substitution:
        from PySubtitle.Substitutions import Substitutions
        options_dict['substitutions'] = Substitutions.Parse(substitution)

    # Create options object
    options = Options(options_dict)

    # Load subtitles
    subtitles = SubtitleFile()
    with open(input_file, 'r', encoding='utf-8') as f:
        srt_content = f.read()
    subtitles.LoadSubtitlesFromString(srt_content)

    # Filter subtitles by time window if requested
    if begin_seconds is not None or end_seconds is not None:
        filtered = []
        for line in subtitles.originals:
            start_sec = line.start.total_seconds() if line.start is not None else None
            end_sec = line.end.total_seconds() if line.end is not None else None
            if start_sec is None or end_sec is None:
                continue
            if begin_seconds is not None and end_sec <= begin_seconds:
                continue
            if end_seconds is not None and start_sec >= end_seconds:
                continue
            filtered.append(line)
        subtitles.originals = filtered
        subtitles._scenes = []
        log(f"Filtered subtitles to {len(filtered)} lines in the time window.")

    # Initialize translation provider
    try:
        provider_obj = TranslationProvider.get_provider(options)
        valid = provider_obj.ValidateSettings()
        if not valid:
            log(f"Invalid provider settings: {provider_obj.validation_message}")
            raise ValueError(f"Invalid provider settings: {provider_obj.validation_message}")
    except Exception as e:
        import traceback
        log(f"Translation provider error: {type(e).__name__}: {e}")
        log(traceback.format_exc())
        raise

    # Set up translator and batching
    from PySubtitle.SubtitleTranslator import SubtitleTranslator
    translator = SubtitleTranslator(options, provider_obj)
    subtitles.AutoBatch(translator.batcher)

    def line_start_seconds(line):
        try:
            return line.start.total_seconds() if line.start is not None else None
        except Exception:
            return None

    def line_end_seconds(line):
        try:
            return line.end.total_seconds() if line.end is not None else None
        except Exception:
            return None

    def batch_end_seconds(batch):
        try:
            return line_end_seconds(batch.originals[-1]) if batch.originals else None
        except Exception:
            return None

    def prioritize_batches_from_timestamp():
        if priority_seconds is None or not subtitles.scenes:
            return
        try:
            timestamp = float(priority_seconds)
        except Exception:
            return

        scene_index = None
        batch_index = 0
        for current_scene_index, scene in enumerate(subtitles.scenes):
            if not scene.batches:
                continue
            scene_end = batch_end_seconds(scene.batches[-1])
            if scene_end is None or scene_end <= timestamp:
                continue
            scene_index = current_scene_index
            for current_batch_index, batch in enumerate(scene.batches):
                batch_end = batch_end_seconds(batch)
                if batch_end is None or batch_end > timestamp:
                    batch_index = current_batch_index
                    break
            break

        if scene_index is None:
            return

        scene = subtitles.scenes[scene_index]
        if batch_index:
            scene.batches = scene.batches[batch_index:] + scene.batches[:batch_index]
        if scene_index:
            subtitles._scenes = subtitles.scenes[scene_index:] + subtitles.scenes[:scene_index]

        first_batch = subtitles.scenes[0].batches[0] if subtitles.scenes[0].batches else None
        if first_batch:
            log(
                "Prioritized subtitle translation from %.1fs at scene %s, batch %s."
                % (timestamp, first_batch.scene, first_batch.number)
            )

    if begin_seconds is None and end_seconds is None:
        prioritize_batches_from_timestamp()

    total_scenes = len(subtitles.scenes)
    flattened_batches = [
        batch
        for scene in subtitles.scenes
        for batch in scene.batches
    ]
    total_batches = len(flattened_batches)

    def batch_coverage_seconds(batch_index):
        try:
            current_batch = flattened_batches[batch_index - 1]
            next_batch = flattened_batches[batch_index] if batch_index < total_batches else None
            if next_batch and next_batch.originals:
                return next_batch.originals[0].start.total_seconds()
            if current_batch.originals:
                return current_batch.originals[-1].end.total_seconds()
        except Exception:
            pass
        return None

    # Progress reporting and batch translation
    orig_translate_batch = translator.TranslateBatch
    progress = {'current': 0}
    def progress_translate_batch(batch, line_numbers, context):
        progress['current'] += 1
        log(f"Translating batch {progress['current']} of {total_batches} (scene {batch.scene}, batch {batch.number})...")
        result = orig_translate_batch(batch, line_numbers, context)
        try:
            subtitles.SaveTranslation(output_file)
            if partial_callback:
                partial_callback(
                    output_file,
                    progress['current'],
                    total_batches,
                    batch_coverage_seconds(progress['current']),
                )
        except Exception as e:
            log(f"\nWarning: Failed to save partial output: {e}")
        return result
    translator.TranslateBatch = progress_translate_batch

    translator.TranslateSubtitles(subtitles)
    log(f"\nTranslation complete. {total_batches} batches processed.")

    # Final save
    subtitles.SaveTranslation(output_file)

def list_provider_models(provider_name, api_key=None):
    """
    List available models for a given provider. Returns a list of model names.
    """
    from PySubtitle.Options import Options
    from PySubtitle.TranslationProvider import TranslationProvider
    options_dict = {'provider': provider_name}
    if api_key:
        options_dict['api_key'] = api_key
    options = Options(options_dict)
    try:
        provider_obj = TranslationProvider.get_provider(options)
        if hasattr(provider_obj, 'available_models'):
            return provider_obj.available_models
        elif hasattr(provider_obj, 'GetAvailableModels'):
            return provider_obj.GetAvailableModels()
        else:
            return []
    except Exception as e:
        return []
