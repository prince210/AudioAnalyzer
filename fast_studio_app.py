import asyncio
import datetime
import gc
import json
import math
import os
import random
import re
import traceback
import uuid
from typing import List

import google.generativeai as genai
import torch
import uvicorn
from fastapi import FastAPI, HTTPException
from google import genai as googleGenAI
from mutagen.wave import WAVE
from pydantic import BaseModel
from google.genai import types

import dynamo_logger
from dynamo_logger import STAGE_NAME

app = FastAPI(title="Fast Studio API")


@app.on_event("startup")
def startup_event():
    """Ensure DynamoDB tables exist on app startup."""
    dynamo_logger.ensure_tables_exist()


from typing import List, Union

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)


def get_gemini_client():
    """Returns googleGenAI Client using GEMINI_API_KEY environment variable."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=500,
            detail="GEMINI_API_KEY environment variable is not configured on the server."
        )
    return googleGenAI.Client(api_key=api_key)


# --- 2. Request Schemas ---
class StoryboardRequest(BaseModel):
    audio_path: Union[List[str], str] = []
    seconds_per_image: int = 10

    # New Jukebox fields
    jukeBox: bool = False
    topics: List[str] = []
    idol: str = ""
    action: str = "sitting peacefully on Mount Kailash, smiling with a divine, glowing aura"


# Image Generation Request
class EffectParams(BaseModel):
    energy_level: float
    pitch_level: float
    motion: str
    transition: str
    overlay: str


class Segment(BaseModel):
    time_range: str
    lyrics_chunk: str
    scene_context: str
    image_prompt: str
    effects: EffectParams


class AudioLyricsImagePrompt(BaseModel):
    status: str
    total_duration_seconds: float
    segments: List[Segment]


class GenerationRequest(BaseModel):
    prompts: list[list[str]]
    song_names: list[str]
    audio_lyrics_image_prompt: List[AudioLyricsImagePrompt] = None


# Song Generation Request
class SongNameGenReq(BaseModel):
    idol: str
    # commasepgenre: str
    totalSongToGenerate: float = 1
    execution_id: str = None


class VideoDescReq(BaseModel):
    topic: str
    song_names: List[str]


class LyricsRequest(BaseModel):
    topic: str = ""
    language: str = "Hindi"
    commasepgenre: str
    existingLyrics: bool = False


class LyricsBatchRequest(BaseModel):
    requests: List[LyricsRequest]
    execution_id: str = None


class TagRequest(BaseModel):
    topics: List
    execution_id: str = None


class ThumbnailRequest(BaseModel):
    topic: str
    style: str = "Spiritual, Devotional"  # Options: Cinematic, Anime, Cyberpunk, 3D Render
    execution_id: str = None


# --- Helper: Gemini Call ---
def call_gemini(prompt: str, system_instruction: str = ""):
    model = genai.GenerativeModel(
        model_name="gemini-2.5-flash",
        system_instruction=system_instruction
    )
    response = model.generate_content(prompt)
    return response.text


def cleanup():
    """Forces RAM and VRAM to release resources."""
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
        torch.cuda.ipc_collect()


def select_prompts(idol):
    match idol:
        case ["Ganesha", "Lord Ganesha"]:
            prompts_list = [
                "{idol} performing {action} while seated on a low wooden platform inside a vibrant temporary structure (pandal) decorated entirely with fresh red hibiscus and yellow marigold flowers,"
                " green leaves, and colorful drapes."
                " The text {song_names} is written on a decorative hanging banner made of flowers and fabric across the top of the frame.",

                "A joyful and dynamic scene. Colorful explosions of dry gulal powder (purple, pink, and yellow) surround {idol} as they perform {action}. "
                "{idol} is smiling and is the clear focal point. The text {song_names} appears in the center, framed by an ornate gold border with floral motifs. Confetti and petals are in the air.",

                "A wide-angle, photorealistic landscape shot of {idol} performing {action} while seated under the massive canopy of an ancient Banyan tree, with hanging roots. "
                "The tree is adorned with bells and marigolds. The text {song_names} is listed clearly on the rough texture of the large tree trunk on the right side of the frame.",

                "{idol} performing {action} while seated on a magnificent, diamond-encrusted gold throne."
                " The background is a deep velvet red curtain. {idol} is richly adorned. The text {song_names} is written in elegant silver lettering on a decorative gold plate "
                "below the throne."
            ]
            return prompts_list
        case ["Lord Shiva", "Shiva"]:
            prompts_list = [
                "{idol} performing {action} on the rugged, snow-covered peak of a majestic mountain. Shiva is depicted with ash-covered skin and long matted hair."
                " The background is a crisp blue sky. The text {song_names} is written in blue, ice-textured lettering on the snowy slope to the right.",

                "A powerful image set against a deep space background filled with distant galaxies, stars, and colorful nebulae. "
                "{idol} is performing {action} (a dynamic dance pose) within a ring of fire. The text {song_names} swirls in a spiral pattern around {idol} in glowing light letters.",

                "A cinematic view of {idol} performing {action} by the edge of a turbulent river, with water dramatically "
                "cascading from their matted hair into the stream. The background shows cliffs and forests. The text {song_names} is listed on a large, smooth rock on the left side of the frame.",

                "A close-up photograph of a massive, decorated iron trident (trishul) with a damaru (small drum) tied to it, planted firmly in the ground. Behind the trishul,"
                " {idol} is seen performing {action} in a softly blurred background. The text {song_names} is listed vertically on a dark leather panel alongside the trishul's shaft.",

                "Inside a dimly lit, ancient stone cave, {idol} is performing {action} while seated near a small, burning sacred fire (dhuni). "
                "The cave walls are covered in moss and simple carvings. The text {song_names} is listed on the smooth cave wall texture on the right in glowing amber letters."
            ]
            return prompts_list
        case ["Lord Vishnu", "Vishnu", "Lord Krishna", "Krishna"]:
            prompts_list = [
                "{idol} performing {action} while reclining on a massive, many-headed serpent floating amidst a calm,"
                "milky white cosmic ocean. The background is a gentle, starry sky. The text {song_names} is placed in the clouds directly above the serpent’s heads.",

                "{idol} performing {action} under a large, blooming Kadamba tree, surrounded by dancing gopis (female devotees) and playful cows."
                " The setting is a beautiful, idyllic garden. The text {song_names} is written on the left side on a decorative panel resembling old parchment, with floral borders.",

                "A glowing, dynamic image. A large, complex golden discus (chakra) with radiant light patterns rotates"
                " directly behind {idol} as they perform {action}. The text {song_names} is positioned in two vertical columns on the left and right, within semi-transparent panels with gold outlines.",

                "Set on the wide plains of an ancient battlefield (like Kurukshetra), {idol} is seen performing {action} on a majestic golden chariot with intricate carvings. "
                "The background shows tents and armies. The text {song_names} is listed clearly on the large, fluttering flag attached to the top of the chariot.",

                "A warm, rustic interior photograph of a traditional Indian kitchen with clay walls, pots, and hanging shelves. {idol} (as a child) is"
                " performing {action} while trying to get butter from a large hanging clay pot. The text {song_names} is written on the side of larger hanging clay pots using a traditional font."
            ]
            return prompts_list
        case ["Goddess Durga", "Durga"]:
            prompts_list = [
                "{idol} performing {action} while riding a powerful lion, radiating a intense, brilliant yellow and red aura of light and energy."
                " The background is a brightly lit temple courtyard with decorative pillars. The text {song_names} is listed on two vertical red and gold fabric banners on either side.",

                "A dynamic, powerful image of {idol} performing {action} while holding multiple weapons in her ten arms,"
                " battling demons in a dark, stormy landscape. Her lion vahana is assisting. The text {song_names} is listed in bold, fiery red and black text at the very bottom."
            ]
            return prompts_list
        case ["Goddess Lakshmi", "Lakshmi"]:
            prompts_list = [
                "{idol} performing {action} while seated gracefully on a giant, pink open lotus flower in the middle of a calm, reflective lake at sunset."
                " The background is a beautiful garden palace. The text {song_names} is written in white letters across the surface of the water.",

                "A radiant and opulent image. A shower of large, golden coins dramatically falls from the sky and cascades down around {idol}"
                " as they perform {action}. {idol} is beautifully adorned in rich fabrics. The text {song_names} is written in high-contrast black font against the shimmering gold background."
            ]
            return prompts_list
        case ["Goddess Saraswati", "Saraswati"]:
            prompts_list = [
                "{idol} performing {action} while seated on a beautiful white swan, playing a Veena (traditional Indian string instrument). "
                "The background is a library with large bookshelves and old books. The text {song_names} is listed on a parchment overlay on the right with calligraphic script."
            ]
            return prompts_list
        case ["Lord Hanuman", "Hanuman"]:
            prompts_list = [
                "A powerful, dynamic depiction of {idol} performing {action} while flying through a dramatic, cloudy sky, holding an entire mountain covered in herbs and trees."
                " The background shows distant landscapes. The text {song_names} is listed on the side of the mountain being carried.",

                "{idol} performing {action} with immense focus, sitting on a stone pedestal at the entrance of an ancient,"
                " decorated stone temple with intricate carvings of deities. The text {song_names} is listed on the steps leading up to the temple.",

                "A moving close-up photograph of {idol} performing {action}. They are in a humble, kneeling posture."
                " In the softly blurred background of a simple temple interior, the text {song_names} appears in a clean, vertical list on a light green panel.",

                "{idol} performing {action} within a dense, lush jungle environment with ancient trees and hanging vines."
                " Sunlight filters through the leaves, creating dappled patterns. The text {song_names} is written on a large, flat, moss-covered rock in the foreground.",

                "{idol} performing {action} while standing on a high cliffside at dawn, with a vibrant orange, pink,"
                " and purple sunrise and a range of mountains in the background. The text {song_names} is listed in the large sky area on the right."
            ]
            return prompts_list
        case ["Lord Rama", "Rama"]:
            prompts_list = [
                "{idol} performing {action} while seated on a golden throne in a magnificent, highly decorated palace hall (like the court of Ayodhya)."
                " Pillars are covered in patterns and lamps. The text {song_names} is written on the royal pillars and decorative archways.",

                "{idol} performing {action} near a small, humble hut made of leaves and wood in a serene forest setting. "
                "{idol} carries a bow and arrow. The text {song_names} is listed on the left side using a rustic, wood-textured font.",

                "A focused side profile photograph of {idol} performing {action} with a beautiful, large golden bow."
                " The background is a dynamic landscape of forests and hills. The text {song_names} is listed along the graceful curve of the bowstring.",

                "{idol} performing {action} by the banks of a calm, wide river during a vibrant sunset with reflection in the water. "
                "Ancient temples are on the distant shore. The text {song_names} is listed on the right side on a soft, glowing yellow panel.",

                "{idol} performing {action} while being formally crowned amidst a large celebration with flowers, decorative drapes, and a procession. "
                "{idol} is smiling. The text {song_names} is listed on a beautiful silk banner held by devotees."
            ]
            return prompts_list
        case _:
            prompts_list = [
                "A cinematic horizontal photograph with a clear 6:4 vertical split. The left section features a highly detailed, photorealistic depiction of {idol} performing {action} "
                "within an ancient, intricately carved stone temple hall at sunset. The right section is a clean, "
                "dark wood-textured panel with the text {song_names} clearly listed in elegant, large gold serif typography. The lighting is warm and devotional.",

                "A wide-angle landscape shot of {idol} performing {action} inside a grand, open-air stone archway. The pillars are covered in detailed carvings of vines and patterns. "
                "To the right of the arch,"
                " on a smooth marble wall surface, the text {song_names} is clearly listed in bold, black lettering, separated by small gold dots. The background shows a lush garden.",

                "An otherworldly, serene scene. {idol} is centered, performing {action} on a massive, glowing pink and white lotus flower floating on a calm, reflective lake. "
                "The background is a soft, misty forest. Multiple ornate, floating text banners surround {idol}, each containing one title from {song_names} in a warm, glowing white script.",

                "A powerful portrait-style image. {idol} is performing {action} while seated on a stone pedestal. Beams of intense, natural sunlight descend from the top-left, creating dramatic light flares and dust motes. "
                "On the right side of the frame, within a sleek, semi-transparent frosted glass panel, the text {song_names} is listed clearly in crisp, white font. The background is softly blurred.",

                "A dynamic image with a large, intricate, rotating geometric pattern (similar to complex flower petal designs in gold and blue) directly behind {idol}. {idol} "
                "is performing {action} and is illuminated by a warm spotlight. The text {song_names} is placed on two vertical, dark velvet panels running along the left and right edges of the frame.",

                "An image of a large, unrolled ancient parchment scroll covering the lower half of the frame. On the upper half, {idol} is depicted performing {action} against a warm, patterned temple wall."
                " The {song_names} are listed clearly on the scroll's textured surface in traditional black calligraphic script. Ancient manuscripts and prayer beads are around the scroll.",

                "A majestic landscape with {idol} performing {action} high above a range of snowy mountain peaks, standing on a fluffy, golden cloud formation. "
                "The background is a vibrant sunrise sky. The text {song_names} is written in a large, bold, white sans-serif font across the bottom third of the image, appearing above the clouds.",

                "A close-up photograph featuring numerous burning traditional oil lamps (diyas) made of clay in the immediate foreground, creating a warm, flickering light. "
                "In the soft-focus background, {idol} is performing {action}. The text {song_names} is listed on the right side of the frame with a glowing warm orange outline.",

                "A sleek, contemporary image with a rich deep saffron-to-purple gradient background. {idol} is performing {action} on the left side, "
                "illuminated by a modern cool-white spotlight. The text {song_names} is listed clearly on the right side within a minimalist layout, featuring a subtle glowing neon effect.",

                "Create a highly detailed, photorealistic devotional poster. The image is split vertically into two halves. Left half: God or Goddess {idol} is performing {action}. "
                "Right half: Featuring a song name {song_names} texts only, keeping the same background as that of left half. Cinematic lighting, 8k resolution, traditional Hindu art style fused with photo realism."
            ]
            return prompts_list


def generate_highlighted_prompts(template, idol, action, song_list):
    response = []
    generated_prompts = []

    # We loop through the song list 5 times.
    for i in range(len(song_list)):
        # Construct the highlighted list of song names
        formatted_songs = []
        for index, song in enumerate(song_list):
            if index == i:
                # This is the active song. We give it strong visual emphasis.
                # Adjust this formatting based on what your AI model prefers.
                # Example: GLOWING GOLD TEXT, LARGER FONT, OR A CURSOR
                highlighted_song = f"[{song.upper()}]"
                formatted_songs.append(highlighted_song)
            else:
                # Standard song. Make it less prominent.
                # Example: Standard white text, slightly faded.
                standard_song = f"[song: {song} (standard white text)]"
                formatted_songs.append(standard_song)

        # Combine the formatted songs into a single string for the prompt
        # Use a clear separator like ' | ' or a new line indicator
        final_song_names_text = " | ".join(formatted_songs)

        # Finally, format the main template
        prompt = template.format(
            idol=idol,
            action=action,
            song_names=final_song_names_text
        )

        generated_prompts.append(prompt)
        response.append({
            "mode": "jukebox",
            "prompts": generated_prompts
        })

    return response


# --- 3. Endpoints ---
@app.post("/generate/thumbnail-prompt")
async def generate_thumbnail_prompt(request: ThumbnailRequest):
    step_name = "GENERATE_THUMBNAIL_PROMPT"
    exec_id = request.execution_id or f"generation_{datetime.datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
    dynamo_logger.log_abstract(STAGE_NAME, step_name, "STARTED",
                               f"Started thumbnail prompt generation for topic: {request.topic}", execution_id=exec_id)
    prompt = f"""
    You are a literal visual scene director. Convert the following lyrics into a SINGLE, 
    highly detailed visual prompt for an image generator. 
    Subject: {request.topic}
    """

    system_instr = f"""
    RULES:
    1. Focus on physical geometry, literal lighting, and traditional cultural accuracy.
    2. DO NOT use abstract metaphors (e.g., "universe of energy").
    3. Output ONLY the raw prompt text. No markdown, no conversational text.
    """

    try:
        response = call_gemini(prompt, system_instr)
        prompt_text = response.strip() if isinstance(response, str) else (
            response.text.strip() if hasattr(response, 'text') else str(response).strip())
        comp_log = dynamo_logger.log_abstract(STAGE_NAME, step_name, "COMPLETED",
                                              "Thumbnail prompt generated successfully", execution_id=exec_id)
        dynamo_logger.log_technical(STAGE_NAME, step_name, "INFO", "Thumbnail prompt generated successfully")

        step_info = {
            "abstract_log_id": comp_log.get("log_id") if comp_log else "",
            "stage": STAGE_NAME,
            "step": step_name,
            "status": "COMPLETED",
            "message": "Thumbnail prompt generated successfully",
            "execution_id": exec_id,
            "timestamp": comp_log.get("timestamp") if comp_log else datetime.datetime.utcnow().isoformat() + "Z"
        }

        return {
            "stage": STAGE_NAME,
            "step": step_name,
            "prompt": prompt_text,
            "steps": [step_info]
        }
    except Exception as e:
        dynamo_logger.log_abstract(STAGE_NAME, step_name, "FAILED", f"Failed to generate thumbnail prompt: {e}",
                                   execution_id=exec_id)
        dynamo_logger.log_technical(STAGE_NAME, step_name, "ERROR", f"Exception in thumbnail prompt generation: {e}",
                                    details=traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/generate/tags")
async def generate_seo_tags(req: TagRequest):
    step_name = "GENERATE_TAGS"
    exec_id = req.execution_id or f"generation_{datetime.datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
    dynamo_logger.log_abstract(STAGE_NAME, step_name, "STARTED",
                               f"Started generating SEO tags for topics: {req.topics}", execution_id=exec_id)
    try:
        client = get_gemini_client()
        topic_names = [f"{idx + 1}. {t}" for idx, t in enumerate(req.topics)]
        print("Generating Tags for topics: ", topic_names)
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=f"You are an SEO expert for YouTube. Read these song names: {topic_names} and output a comma-separated "
                     "list of 15 highly searched, relevant YouTube tags. No other text."
        )
        processed_list = [item.strip() for item in response.text.split(',')]
        print("Generating Tags for topics: ", topic_names)
        print("Generating Tags Response retrieved : ", processed_list)
        comp_log = dynamo_logger.log_abstract(STAGE_NAME, step_name, "COMPLETED",
                                              f"Generated {len(processed_list)} SEO tags successfully",
                                              execution_id=exec_id)
        dynamo_logger.log_technical(STAGE_NAME, step_name, "INFO", f"Generated SEO tags: {processed_list}")

        step_info = {
            "abstract_log_id": comp_log.get("log_id") if comp_log else "",
            "stage": STAGE_NAME,
            "step": step_name,
            "status": "COMPLETED",
            "message": f"Generated {len(processed_list)} SEO tags successfully",
            "execution_id": exec_id,
            "timestamp": comp_log.get("timestamp") if comp_log else datetime.datetime.utcnow().isoformat() + "Z"
        }

        return {
            "stage": STAGE_NAME,
            "step": step_name,
            "tags": processed_list,
            "steps": [step_info]
        }
    except Exception as e:
        dynamo_logger.log_abstract(STAGE_NAME, step_name, "FAILED", f"Failed to generate SEO tags: {e}",
                                   execution_id=exec_id)
        dynamo_logger.log_technical(STAGE_NAME, step_name, "ERROR", f"Exception in generate_seo_tags: {e}",
                                    details=traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


# v2 lyrics
@app.post("/generate/lyrics")
async def generate_lyrics_with_gemini(request: LyricsBatchRequest):
    step_name = "GENERATE_LYRICS"
    exec_id = request.execution_id or f"generation_{datetime.datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
    dynamo_logger.log_abstract(STAGE_NAME, step_name, "STARTED",
                               f"Started lyrics generation batch for {len(request.requests)} request(s)",
                               execution_id=exec_id)
    try:
        results = []
        chunk_size = 5
        for i in range(0, len(request.requests), chunk_size):
            chunk = request.requests[i:i + chunk_size]

            for req in chunk:
                if req.existingLyrics:
                    print(f"Getting existing lyrics")
                    prompt = (f"""
                                1. Fetch original LYRICS for the devotional song about: '{req.topic}' in '{req.language} language' only. Do NOT generate a summary or a new lyrics, generated lyrics should exactly match existing lyrics. Only output the original, non empty LYRICS from non copyright source."
                                2. Based on LYRICS obtained in step 1. Generate {req.commasepgenre} STYLE for songs in 4 to 5 words separated by comma to enhance the song hearing experience based on indian culture bhajan style.
                              """)
                    tags = "[LYRICS]...[STYLE]"
                    system_instruction = (
                        f"""
                            1. You are a professional hit-making songwriter. Get LYRICS structured with #Verse#, #Chorus#, and #Bridge#. Do not provide anything else than lyrics."
                            2. LYRICS should not be empty.
                            3. OUTPUT FORMAT:
                            You must use these exact markers. Do not include any other text.
                            {tags}
                        """)

                    try:
                        lyrics_styles = call_gemini(prompt, system_instruction) + "["
                        patterns = {
                            "summary": r"\[SUMMARY\](.*?)\[",
                            "lyrics": r"\[LYRICS\](.*?)\[",
                            "style": r"\[STYLE\](.*?)\["
                        }

                        print(f"LYRICS STYLES GENERATED ----> \n {lyrics_styles}")

                        result = {}
                        for key, pattern in patterns.items():
                            match = re.search(pattern, lyrics_styles, re.DOTALL | re.IGNORECASE)
                            result[key] = match.group(1).strip() if match else None

                        print(f"""Lyrics generated {result["lyrics"]}""")
                        print(f"""Styles generated {result["style"]}""")

                        splitted_lyrics = list(filter(None, re.split(r'[ ,;]+', str(result["lyrics"]))))

                        if len(splitted_lyrics) < 5:
                            result["lyrics"] = (result["lyrics"] + ".") * 11

                        results.append(
                            {
                                "status": "success",
                                "topic": req.topic,
                                "language": req.language,
                                "lyrics": result["lyrics"],
                                "style": result["style"]
                            }
                        )

                    except Exception as e:
                        dynamo_logger.log_technical(STAGE_NAME, step_name, "ERROR",
                                                    f"Error fetching existing lyrics for topic '{req.topic}': {e}",
                                                    details=traceback.format_exc())
                        fail_log = dynamo_logger.log_abstract(STAGE_NAME, step_name, "FAILED",
                                                              f"Error fetching existing lyrics: {e}",
                                                              execution_id=exec_id)
                        step_info = {
                            "abstract_log_id": fail_log.get("log_id") if fail_log else "",
                            "stage": STAGE_NAME,
                            "step": step_name,
                            "status": "FAILED",
                            "message": f"Error fetching existing lyrics: {e}",
                            "execution_id": exec_id,
                            "timestamp": fail_log.get(
                                "timestamp") if fail_log else datetime.datetime.utcnow().isoformat() + "Z"
                        }
                        return {"stage": STAGE_NAME, "step": step_name, "status": "error", "message": str(e),
                                "steps": [step_info]}

                else:
                    print(f"Generating more than 700 character summary in {req.language} about {req.topic}...")

                    system_prompt = (
                        f"Generate summary about '{req.topic}' "
                        f"in the {req.language} language. Generate summary in more than 700 characters"
                        f"Should have mixture of complex and simple words.\n"
                    )

                    system_instruction = ("You are a professional hit-making songwriter. Ensure summary is "
                                          "emotional, catchy, goosebumps.")

                    try:
                        summary = call_gemini(system_prompt, system_instruction)
                        print(f"summary generated {summary}")

                    except Exception as e:
                        dynamo_logger.log_technical(STAGE_NAME, step_name, "ERROR",
                                                    f"Error generating summary for topic '{req.topic}': {e}",
                                                    details=traceback.format_exc())
                        fail_log = dynamo_logger.log_abstract(STAGE_NAME, step_name, "FAILED",
                                                              f"Error generating summary: {e}", execution_id=exec_id)
                        step_info = {
                            "abstract_log_id": fail_log.get("log_id") if fail_log else "",
                            "stage": STAGE_NAME,
                            "step": step_name,
                            "status": "FAILED",
                            "message": f"Error generating summary: {e}",
                            "execution_id": exec_id,
                            "timestamp": fail_log.get(
                                "timestamp") if fail_log else datetime.datetime.utcnow().isoformat() + "Z"
                        }
                        return {"stage": STAGE_NAME, "step": step_name, "status": "error", "message": str(e),
                                "steps": [step_info]}

                    print(f"Generating a minimum 2-minute {req.language} song about {req.topic}...")
                    system_instruction = (
                        f"""
                        You are a professional hit-making songwriter. Write lyrics that are devotional, emotional, catchy, and structured with [Verse], [Chorus], and [Bridge]. Ensure consistent structured rhyme"
                        """)
                    prompt = (
                        f"""
                            Analyze the provided summary {summary} and write a song in {req.language} language 
                            relying heavily on mixture of complex and simple {req.language} words that follow Rhythm and rhyme glorifying the deity in devotional 
                            way giving goosebumps. Structure song with [Verse], [Chorus], and [Bridge]. Only return the lyrics.
                        """
                    )

                    try:
                        lyrics = call_gemini(prompt, system_instruction)
                        print(f"LYRICS \n {lyrics}")
                        prompt = f"Provided the devotional hindi lyrics as {lyrics}. Do NOT generate a summary or a new song. Only output the style in which it should be sung for better hearing experience."
                        system_instruction = (
                            f"""
                                You are a professional hit-making songwriter. Generate artistic styles in 3 to 4 words comma separated to enhance the song hearing experience."
                            """)

                        styles_generated = call_gemini(prompt, system_instruction)

                        print(f"Styles generated {styles_generated}")

                        results.append({
                            "status": "success",
                            "topic": req.topic,
                            "language": req.language,
                            "lyrics": lyrics,
                            "style": styles_generated
                        })

                    except Exception as e:
                        dynamo_logger.log_technical(STAGE_NAME, step_name, "ERROR",
                                                    f"Error generating lyrics for topic '{req.topic}': {e}",
                                                    details=traceback.format_exc())
                        fail_log = dynamo_logger.log_abstract(STAGE_NAME, step_name, "FAILED",
                                                              f"Error generating lyrics: {e}", execution_id=exec_id)
                        step_info = {
                            "abstract_log_id": fail_log.get("log_id") if fail_log else "",
                            "stage": STAGE_NAME,
                            "step": step_name,
                            "status": "FAILED",
                            "message": f"Error generating lyrics: {e}",
                            "execution_id": exec_id,
                            "timestamp": fail_log.get(
                                "timestamp") if fail_log else datetime.datetime.utcnow().isoformat() + "Z"
                        }
                        return {"stage": STAGE_NAME, "step": step_name, "status": "error", "message": str(e),
                                "steps": [step_info]}

            if i + chunk_size < len(request.requests):
                print(f"⏳ Reached API limit (4 requests). Waiting 60 seconds before continuing...")
                await asyncio.sleep(60)

        comp_log = dynamo_logger.log_abstract(STAGE_NAME, step_name, "COMPLETED",
                                              f"Completed batch lyrics generation for {len(results)} request(s)",
                                              execution_id=exec_id)
        dynamo_logger.log_technical(STAGE_NAME, step_name, "INFO",
                                    f"Lyrics generation completed successfully for {len(results)} items")

        step_info = {
            "abstract_log_id": comp_log.get("log_id") if comp_log else "",
            "stage": STAGE_NAME,
            "step": step_name,
            "status": "COMPLETED",
            "message": f"Completed batch lyrics generation for {len(results)} request(s)",
            "execution_id": exec_id,
            "timestamp": comp_log.get("timestamp") if comp_log else datetime.datetime.utcnow().isoformat() + "Z"
        }

        return {
            "stage": STAGE_NAME,
            "step": step_name,
            "status": "completed",
            "total_processed": len(results),
            "data": results,
            "steps": [step_info]
        }
    except Exception as e:
        dynamo_logger.log_abstract(STAGE_NAME, step_name, "FAILED", f"Failed lyrics generation batch: {e}",
                                   execution_id=exec_id)
        dynamo_logger.log_technical(STAGE_NAME, step_name, "ERROR", f"Exception in generate_lyrics_with_gemini: {e}",
                                    details=traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/generate/storyboard")
async def generate_storyboard(req: StoryboardRequest):
    step_name = "GENERATE_STORYBOARD"
    dynamo_logger.log_abstract(STAGE_NAME, step_name, "STARTED",
                               f"Started storyboard generation (jukeBox={req.jukeBox})")
    try:
        response = []
        if req.jukeBox:
            topics_formatted = "\n ".join([f"{idx + 1}. {t}" for idx, t in enumerate(req.topics)])
            notes = [f"Image should only contain {topics_formatted} texts only. No other text or alien characters."
                , f"Image should be clear and blur free"]
            selected_template = random.choice(select_prompts(
                req.idol)) + f".NOTE - Image should only contain {topics_formatted} texts only. No other text or alien characters."
            result_data = generate_highlighted_prompts(selected_template, req.idol, req.action, req.topics)
            dynamo_logger.log_abstract(STAGE_NAME, step_name, "COMPLETED",
                                       "Jukebox storyboard prompt generated successfully")
            dynamo_logger.log_technical(STAGE_NAME, step_name, "INFO",
                                        "Jukebox storyboard prompt generated successfully")
            return {
                "stage": STAGE_NAME,
                "step": step_name,
                "status": "completed",
                "response": result_data
            }
        else:
            audio_paths = [req.audio_path] if isinstance(req.audio_path, str) else req.audio_path
            for audio_file in audio_paths:
                try:
                    audio = WAVE(audio_file)
                    total_seconds = int(audio.info.length)
                    print(f"Total audio length in seconds: {total_seconds}")
                    num_prompts = math.ceil(total_seconds / req.seconds_per_image)
                except Exception as e:
                    print(f"Audio read error, defaulting to 15 prompts. Error: {e}")
                    total_seconds = 150
                    num_prompts = 15

                summary_prompt = f"""
                Write 6 simple, plain-English summaries about the topic: '{req.topics}'.
                """
                summaries = call_gemini(summary_prompt
                                        ,
                                        f"Focus on devotion, physical rituals, temples, and human emotions. DO NOT use complex "
                                        f"cosmic or abstract words.")

                prompt = f"""
                You are a literal visual scene director. Based on these summaries:\n{summaries}\n
                Create exactly {num_prompts} physical, simple visual prompts elaborately providing better context to other model.
                Subject: {req.topics}.
                """

                prompt_system_instr = f""" RULES: 1. DO NOT use abstract metaphors (e.g., "energy of the universe", "soul of the 
                world"). AI cannot draw this. 2. DO use physical, geometric descriptions, concrete objects, and literal 
                environments. 3. BAD EXAMPLE: "Lord Shiv's aniconic form radiating immense golden energy into every atom." 4. 
                GOOD EXAMPLE: "Lord Shiv in shiv ling form (a cylindrical black stone sitting on a circular base), glowing golden 
                light emitting from behind it in a circular shape, devotees sitting on the floor in front of it." 5. Ensure 
            {req.topics} is physically described in every prompt.
                6. Output ONLY a valid JSON list of {num_prompts} strings.
                """

                gemini_resp = call_gemini(prompt, prompt_system_instr)
                raw_content = gemini_resp.strip() if isinstance(gemini_resp, str) else (
                    gemini_resp.text.strip() if hasattr(gemini_resp, 'text') else str(gemini_resp).strip())

                clean_text = re.sub(r'```json|```', '', raw_content).strip()
                parsed_prompts = []
                try:
                    parsed_prompts = json.loads(clean_text)
                except json.JSONDecodeError:
                    print("Falling back to Regex parser for storyboard...")
                    matches = re.findall(r'"([^"]*)"', clean_text)
                    if matches:
                        parsed_prompts = matches
                    else:
                        raise HTTPException(status_code=500, detail="Failed to parse LLM output into a list.")

                response.append({
                    "mode": "exclusive",
                    "total_audio_seconds": total_seconds,
                    "prompts_generated": len(parsed_prompts),
                    "prompts": parsed_prompts,
                    "summaries_gen": summaries
                })
            dynamo_logger.log_abstract(STAGE_NAME, step_name, "COMPLETED", "Storyboard prompts generated successfully")
            dynamo_logger.log_technical(STAGE_NAME, step_name, "INFO", "Storyboard prompts generated successfully")
            return {
                "stage": STAGE_NAME,
                "step": step_name,
                "status": "completed",
                "response": response
            }
    except Exception as e:
        dynamo_logger.log_abstract(STAGE_NAME, step_name, "FAILED", f"Failed to generate storyboard: {e}")
        dynamo_logger.log_technical(STAGE_NAME, step_name, "ERROR", f"Exception in generate_storyboard: {e}",
                                    details=traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/generate/song-names")
async def generate_song_names(req: SongNameGenReq):
    step_name = "GENERATE_SONG_NAMES"
    exec_id = req.execution_id or f"generation_{datetime.datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
    dynamo_logger.log_abstract(STAGE_NAME, step_name, "STARTED",
                               f"Started generating {req.totalSongToGenerate} song name(s) for idol: {req.idol}",
                               execution_id=exec_id)
    try:
        client = get_gemini_client()

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=f"generate top {req.totalSongToGenerate} popular non copyright"
                     f" hindi song name based on {req.idol}. "
                     f"CRITICAL : Return only comma separated song names no other text",
        )

        processed_list = [item.strip() for item in response.text.split(',')]
        print(processed_list)
        comp_log = dynamo_logger.log_abstract(STAGE_NAME, step_name, "COMPLETED",
                                              f"Generated {len(processed_list)} song name(s) successfully",
                                              execution_id=exec_id)
        dynamo_logger.log_technical(STAGE_NAME, step_name, "INFO", f"Generated song names: {processed_list}")

        step_info = {
            "abstract_log_id": comp_log.get("log_id") if comp_log else "",
            "stage": STAGE_NAME,
            "step": step_name,
            "status": "COMPLETED",
            "message": f"Generated {len(processed_list)} song name(s) successfully",
            "execution_id": exec_id,
            "timestamp": comp_log.get("timestamp") if comp_log else datetime.datetime.utcnow().isoformat() + "Z"
        }

        return {
            "stage": STAGE_NAME,
            "step": step_name,
            "song_names": processed_list,
            "steps": [step_info]
        }
    except Exception as e:
        dynamo_logger.log_abstract(STAGE_NAME, step_name, "FAILED", f"Failed to generate song names: {e}",
                                   execution_id=exec_id)
        dynamo_logger.log_technical(STAGE_NAME, step_name, "ERROR", f"Exception in generate_song_names: {e}",
                                    details=traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/generate/video/description")
async def generate_video_description(req: VideoDescReq):
    step_name = "GENERATE_VIDEO_DESCRIPTION"
    dynamo_logger.log_abstract(STAGE_NAME, step_name, "STARTED",
                               f"Started video description generation for topic: {req.topic}")
    try:
        client = get_gemini_client()
        songs_formatted = "\n ".join([f"{idx + 1}. {t}" for idx, t in enumerate(req.song_names)])

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=f"generate seo optimized description for youtube video for {req.topic} topic containing following "
                     f"songs {songs_formatted} in mostly hindi language and use little bit english also."
                     f"CRITICAL : Return only seo optimized description.",
        )

        response_txt = response.text
        print(response_txt)
        dynamo_logger.log_abstract(STAGE_NAME, step_name, "COMPLETED", "Video description generated successfully")
        dynamo_logger.log_technical(STAGE_NAME, step_name, "INFO", "Video description generated successfully")
        return {
            "stage": STAGE_NAME,
            "step": step_name,
            "video_description": response_txt
        }
    except Exception as e:
        dynamo_logger.log_abstract(STAGE_NAME, step_name, "FAILED", f"Failed to generate video description: {e}")
        dynamo_logger.log_technical(STAGE_NAME, step_name, "ERROR", f"Exception in generate_video_description: {e}",
                                    details=traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))





def clean_text(text):
    # remove escape sequences
    text = re.sub(r'[\n\r\t]', ' ', text)
    # remove extra spaces
    text = re.sub(r'\s+', ' ', text).strip()
    # replace single spaces with underscore
    text = text.replace(' ', '_')
    return text


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8020)

# [["An otherworldly, serene scene. Vishnu is centered, performing A highly detailed and dramatic artistic depiction of Lord Vishnu in His Vishwaroopam (Universal Form). Infinite heads and arms, cosmic elements like galaxies, stars, and planets within his body. A radiant aura of divine energy, epic, powerful, digital fantasy painting, Bhagavad Gita scene. on a massive, glowing pink and white lotus flower floating on a calm, reflective lake. The background is a soft, misty forest. Multiple ornate, floating text banners surround Vishnu, each containing one title from [ACTIVE SONG: ** VISHNU STOTRAM ** (GLOWING GOLD TEXT)] in a warm, glowing white script..NOTE - "]]

# [["A close-up photograph featuring numerous burning traditional oil lamps (diyas) made of clay in the immediate foreground, creating a warm, flickering light. In the soft-focus background, Vishnu is performing A highly detailed and dramatic artistic depiction of Lord Vishnu in His Vishwaroopam (Universal Form). Infinite heads and arms, cosmic elements like galaxies, stars, and planets within his body. A radiant aura of divine energy, epic, powerful, digital fantasy painting, Bhagavad Gita scene.. The text [VISHNU STOTRAM] is listed on the right side of the frame with a glowing warm orange outline..NOTE - "]]
