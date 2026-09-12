# below is previous implementation V1.0

#
# import json
# from faster_whisper import WhisperModel
# import ollama
#
#
# def analyze_audio(file_path, lyric):
#     # 1. Transcribe using faster-whisper (utilizing your RTX 4060 via CUDA)
#     model = WhisperModel("base", device="cuda", compute_type="float16")
#     segments, _ = model.transcribe(file_path, beam_size=5)
#     full_text = " ".join([s.text for s in segments])
#
#     # 2. Generate Prompt using Ollama (Llama 3.2 or Mistral)
#     # This identifies the "vibe" and creates visual prompts for your images
#     system_prompt = (
#         "You are a visual director for devotional videos. Analyze the lyrics "
#         "and provide 12-15 highly detailed cinematic prompts for image generation."
#     )
#
#     print(f"Starting generation on: {full_text}")
#
#     response = ollama.generate(
#         model='llama3.2',
#         prompt=f"{system_prompt}\n\nLyrics: {lyric}"
#     )
#
#     # 3. Output as JSON for Java to read
#     result = {
#         "transcription": full_text,
#         "visual_prompts": response['response']
#     }
#     print(json.dumps(result))
#
#
# if __name__ == "__main__":
#     # audio_input = sys.argv[1]
#     test_audio_path = r"C:\Prince projects\YoutubeAutomate\WebCrawler\audio\track_0.wav"
#     lyrics = r"डमरू की डम-डम से गूंजा, अंबर का हर कोना है,\nशून्य से जो जागा है, वही मृत्यु का बिछौना है।\nजटाओं के उस जाल में, गंगा का वेग समाया है,\nत्रिलोकी के इस नाथ ने, आज तांडव रचाया है।\n\nमस्तक पर है चंद्र विराजे, भाल पे धधके ज्वाला है,\nगले में लिपटा काल सर्प, मुंडों की पहनी माला है।\nव्याघ्र चर्म की ओढ़नी, भस्म लेप अंग-अंग सजे,\nएक पग जो धरती पे पड़े, तो सात स्वर्ग भी कांप उठे।\n\nधिमि-धिमि मृदंग के स्वर संग, ता-थैया की थपकी है,\nविनाश की इस लय में ही, सृजन की गहरी झपकी है।\nअंधकार के पाश काटते, शिव का तीसरा नयन खुला,\nअहंकार की राख बनी, जब रुद्र का यह रूप ढला।\n\nन राजा बड़ा न रंक बड़ा, न शत्रु कोई न मीत यहाँ,\nशिव की इस चौखट पे तो, बस भक्ति की ही प्रीत यहाँ।\nजब-जब डोले त्रिशूल हाथ में, अधर्म का सर्वनाश हो,\nहे महादेव! इस तांडव से, अंतःकरण का प्रकाश हो।"
#     print(f"Starting analysis on: {test_audio_path}")
#     analyze_audio(test_audio_path, lyrics)

# Latest implemetation V1.1

import ollama
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn


app = FastAPI()


# --- Request Models ---
class LyricsRequest(BaseModel):
    lyrics_text: str


@app.post("/generate/lyrics")
def analyze_lyrics_to_prompts(lyricsText: LyricsRequest):
    system_prompt = (
        "You are a visual director for devotional videos. Analyze the following lyrics "
        "and provide EXACTLY 15 highly detailed, cinematic visual prompts for Stable Diffusion. "
        "Respond ONLY with a valid JSON array of strings. Do not include any other text, markdown, or explanations."
    )

    print("Analyzing lyrics with Ollama...")

    response = ollama.generate(
        model='llama3.2',
        prompt=f"{system_prompt}\n\nLyrics:\n{lyricsText.lyrics_text}"
    )

    # The output is perfectly formatted JSON ready to be passed to the image generator
    raw_output = response['response']
    print("\n--- Generated Prompts ---")
    print(raw_output)

    return raw_output


if __name__ == "__main__":
    # test_lyrics = """
    # महा शिव रात्रि की मूल कहानी:\n\n**Verse 1**\n(गूझबूंप वाली शुरुआत)\nमैंने सुना था एक दिलचस्प कथा\nभगवान शिव ने पार्वती को चंद्रमा की तरह देखा\nउनकी बेटी काली के साथ मिलने जाने के लिए\nएक रात्रि का निर्वहन करने का फैसला\n\n**Chorus**\n(मेलोडी वाला चोरस)\nमहा शिव रात्रि, एक पवित्र और रहस्यमय पर्व\nभगवान शिव की भक्ति और पूजन को व्यक्त करने का अवसर\nहमें अपने दिलों से उनकी पूजा करनी चाहिए\nमहा शिव रात्रि, एक खूबसूरत पर्व\n\n**Verse 2**\n(रैप स्टाइल)\nयह कहानी हमें सिखाती है कि भक्ति और प्रेम क्या है\nजब भगवान शिव ने अपनी पत्नी को चंद्रमा की तरह देखा\nउन्होंने अपने सिर पर एक तिलक लगाया था\nअब हम भी ऐसा करने का अवसर पा रहे हैं\n\n**Chorus**\n(मेलोडी वाला चोरस)\nमहा शिव रात्रि, एक पवित्र और रहस्यमय पर्व\nभगवान शिव की भक्ति और पूजन को व्यक्त करने का अवसर\nहमें अपने दिलों से उनकी पूजा करनी चाहिए\nमहा शिव रात्रि, एक खूबसूरत पर्व\n\n**Bridge**\n(लोफी स्टाइल)\nजैसे ही ध्यान और प्रार्थना में व्यस्त होते हैं\nहम भगवान शिव को अरध्या स्थापित करते हैं\nउनकी दास्तान सुनने के लिए आमंत्रित किया जाता है\nऔर उनकी पूजन और आराधना की जाती है\n\n**Outro**\n(गूझबूंप वाली समाप्ति)\nमहा शिव रात्रि, एक बहुत ही खूबसूरत पर्व\nभगवान शिव की भक्ति और पूजन को व्यक्त करने का अवसर\nहमें अपने दिलों से उनकी पूजा करनी चाहिए\nमहा शिव रात्रि, एक यादगार पर्व।
    # """
    # analyze_lyrics_to_prompts(test_lyrics)
    uvicorn.run(app, host="0.0.0.0", port=8030)