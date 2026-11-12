
import json
import os
import re
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

CHANNEL_ID = "UCzgxx_DM2Dcb9Y1spb9mUJA"
MODEL = "gemini-3.8-flash"

ATOM = "{http://www.w3.org/2005/Atom}"
YT = "{http://www.youtube.com/xml/schemas/2015}"
MEDIA = "{http://search.yahoo.com/mrss/}"


def get_latest_videos():
    url = (
        "https://www.youtube.com/feeds/videos.xml"
        f"?channel_id={CHANNEL_ID}"
    )

    request = urllib.request.Request(
        url, headers={"User-Agent": "TWICE-Shorts-Research/1.0"}
    )

    with urllib.request.urlopen(request, timeout=30) as response:
        root = ET.fromstring(response.read())

    videos = []

    for entry in root.findall(f"{ATOM}entry")[:5]:
        video_id = entry.findtext(f"{YT}videoId")
        title = entry.findtext(f"{ATOM}title", "Untitled")
        published = entry.findtext(f"{ATOM}published", "")

        link_element = entry.find(f"{ATOM}link")
        link = (
            link_element.get("href", "")
            if link_element is not None
            else f"https://www.youtube.com/watch?v={video_id}"
        )

        description = ""
        group = entry.find(f"{MEDIA}group")
        if group is not None:
            description = group.findtext(
                f"{MEDIA}description", ""
            )

        videos.append({
            "video_id": video_id,
            "title": title,
            "published": published,
            "url": link,
            "description": description[:1500],
        })

    if not videos:
        raise RuntimeError("No videos found in the channel feed.")

    return videos


def research_with_gemini(videos):
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY secret is missing.")

    prompt = f"""
You are a K-pop Shorts content researcher.

Analyze these recent public uploads from TWICE's official channel.

VIDEO METADATA:
{json.dumps(videos, ensure_ascii=False, indent=2)}

Return valid JSON only, using this structure:

{{
  "research_summary": "Short summary",
  "ideas": [
    {{
      "source_video_id": "ID from supplied metadata",
      "source_title": "Exact supplied title",
      "shorts_concept": "Original creative concept",
      "hook": "Opening hook",
      "editing_direction": "Suggested editing approach",
      "caption_ideas": ["Caption 1", "Caption 2"],
      "narration": "Optional original narration",
      "original_value": "How this adds meaningful creative value",
      "evidence_status": "metadata_only",
      "timestamp": null
    }}
  ]
}}

Rules:
- Generate at most 5 ideas.
- Use only the supplied video metadata.
- Do not invent events, dialogue, member actions or timestamps.
- Do not claim to have watched the videos.
- Keep concepts funny, entertaining and suitable for K-pop fans.
- Suggest original commentary or storytelling, not simple reposts.
- Use only source video IDs supplied above.
- If metadata is insufficient, say so explicitly.
"""

    endpoint = (
        "https://generativelanguage.googleapis.com/v1beta/"
        f"models/{MODEL}:generateContent"
    )

    payload = {
        "contents": [{
            "parts": [{"text": prompt}]
        }],
        "generationConfig": {
            "responseMimeType": "application/json",
            "temperature": 0.4,
            "maxOutputTokens": 2500
        }
    }

    request = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": api_key,
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            result = json.loads(response.read())

    except urllib.error.HTTPError as error:
        details = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"Gemini API returned HTTP {error.code}: {details[:1500]}"
        ) from error

    text = result["candidates"][0]["content"]["parts"][0]["text"]
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())

    return json.loads(text)


def main():
    print("Checking TWICE channel uploads...")
    videos = get_latest_videos()
    print(f"Found {len(videos)} recent videos.")

    print("Sending video metadata to Gemini...")
    research = research_with_gemini(videos)

    output = {
        "source_channel_id": CHANNEL_ID,
        "videos_checked": videos,
        "ai_research": research,
    }

    report_dir = Path("reports")
    report_dir.mkdir(exist_ok=True)

    output_path = report_dir / "discovery.json"
    output_path.write_text(
        json.dumps(output, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(f"Research completed: {output_path}")
    print(json.dumps(research, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
