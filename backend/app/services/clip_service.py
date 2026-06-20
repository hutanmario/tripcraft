"""
clip_service.py
Serviciu CLIP pentru generarea automată de taguri din imagini.
Folosește zero-shot classification — nu necesită training pe datele noastre.
"""

from transformers import CLIPProcessor, CLIPModel
from PIL import Image
import requests
import torch
import io
import numpy as np
import colorsys
from typing import Optional
import logging

logger = logging.getLogger(__name__)

# Tagurile noastre din DB — CLIP va scora fiecare imagine față de toate
TRAVEL_TAGS = [
    "beach", "mountain", "city", "nature", "adventure", "culture",
    "history", "architecture", "gastronomy", "nightlife", "romantic",
    "family-friendly", "hiking", "skiing", "wellness", "photography",
    "wildlife", "local-culture", "festivals", "shopping", "offbeat",
    "ancient-ruins", "castles", "national-park", "lake", "waterfalls",
    "desert", "forest", "island", "coastal", "urban", "rural",
    "luxury", "budget", "mid-range", "summer", "winter", "spring",
    "autumn", "year-round", "warm", "cold", "temperate", "mediterranean",
    "nordic", "tropical", "art", "museums", "street-food", "wine-tasting",
    "diving", "surfing", "climbing", "cycling", "yoga", "spa",
    "religious", "unesco", "traditional", "modern", "industrial",
]

# Descrieri mai naturale pentru CLIP — funcționează mai bine cu fraze
TAG_PROMPTS = {
    "beach": "a beautiful sandy beach with ocean waves",
    "mountain": "majestic mountain peaks and alpine scenery",
    "city": "a vibrant urban cityscape with buildings",
    "nature": "pristine natural landscape and wilderness",
    "adventure": "exciting outdoor adventure activities",
    "culture": "rich cultural heritage and traditions",
    "history": "ancient historical sites and ruins",
    "architecture": "impressive architectural buildings and structures",
    "gastronomy": "delicious local food and cuisine",
    "nightlife": "vibrant nightlife bars and entertainment",
    "romantic": "romantic scenery perfect for couples",
    "family-friendly": "family friendly activities and attractions",
    "hiking": "scenic hiking trails through nature",
    "skiing": "ski slopes and winter sports resort",
    "wellness": "relaxing spa and wellness retreat",
    "photography": "stunning scenic views for photography",
    "wildlife": "exotic wildlife and animals in nature",
    "local-culture": "authentic local culture and community",
    "festivals": "colorful cultural festivals and celebrations",
    "shopping": "markets and shopping districts",
    "offbeat": "hidden gem off the beaten path destination",
    "ancient-ruins": "ancient archaeological ruins and temples",
    "castles": "medieval castle and fortress",
    "national-park": "protected national park with nature",
    "lake": "serene lake and waterfront scenery",
    "waterfalls": "magnificent waterfall in nature",
    "desert": "vast desert landscape and sand dunes",
    "forest": "dense forest with tall trees",
    "island": "tropical island paradise",
    "coastal": "beautiful coastal cliffs and shoreline",
    "urban": "modern urban city environment",
    "rural": "peaceful rural countryside",
    "luxury": "luxury resort and upscale accommodation",
    "budget": "affordable budget travel destination",
    "mid-range": "comfortable mid-range travel destination",
    "summer": "summer vacation destination with sunshine",
    "winter": "winter wonderland with snow",
    "warm": "warm sunny tropical climate",
    "cold": "cold arctic or mountain climate",
    "temperate": "mild temperate climate destination",
    "mediterranean": "mediterranean sea and coastal towns",
    "art": "art galleries and creative districts",
    "museums": "world class museums and exhibitions",
    "street-food": "vibrant street food markets",
    "wine-tasting": "wine vineyards and tasting tours",
    "diving": "crystal clear water for scuba diving",
    "surfing": "perfect waves for surfing",
    "climbing": "rock climbing and mountaineering",
    "cycling": "scenic cycling routes and bike paths",
    "spa": "luxury spa and thermal baths",
    "religious": "sacred religious sites and temples",
    "unesco": "UNESCO world heritage site",
    "traditional": "traditional customs and folk culture",
    "modern": "modern contemporary architecture and design",
}


# Taguri abstracte care nu au semnal vizual detectabil în imagini.
# Climatul, bugetul și hobby-uri meta nu pot fi deduse dintr-o fotografie —
# apar ca false positives deoarece prompt-urile lor se potrivesc generic cu
# orice imagine de travel. Vor fi atribuite destinațiilor prin quiz sau manual.
CLIP_EXCLUDED_TAGS = {
    # Climatic — se decide din quiz, nu din imagine
    "temperate", "year-round", "cold", "warm", "mild-climate",
    # Buget — se decide din întrebare hardcodată în quiz
    "budget", "mid-range", "luxury",
    # Meta-hobby — nu e intenție de călătorie detectabilă vizual
    "photography",
    # Generic fără valoare semantică pentru clasificare vizuală
    "tours", "unique-experience", "unique-stays",
    # Sezoniere și climatice-regionale — fără semnal vizual real
    "summer", "winter", "spring", "autumn",
    "mediterranean", "nordic", "tropical",
    "continental", "oceanic",
}


SCENE_PROMPTS = {
    "indoor": "a photo taken inside a building indoors",
    "outdoor": "a photo taken outside in open air",
    "urban": "a city street urban environment with buildings",
    "natural": "nature wilderness landscape without buildings",
    "crowded": "a crowded place with many people",
    "peaceful": "a quiet peaceful empty place",
    "daytime": "a photo taken during the day in daylight",
    "nighttime": "a photo taken at night in darkness",
    "landmark": "a famous landmark tourist attraction monument",
    "food": "food meal restaurant cuisine dish plate",
    "beach": "beach sea ocean coastline waves sand",
    "mountain": "mountain peak summit highland alpine snow",
}

COLOR_TO_TAGS = {
    "blue_deep":   {"beaches": 0.3, "swimming": 0.2, "sailing": 0.2, "scuba-diving": 0.15},
    "blue_light":  {"beaches": 0.2, "lake-swimming": 0.2, "kayaking-canoeing": 0.15},
    "green_dark":  {"hiking": 0.3, "forests": 0.25, "wildlife-nature": 0.2, "camping": 0.15},
    "green_light": {"cycling-biking": 0.2, "countryside-walks": 0.2, "photography-landscapes": 0.15},
    "white_grey":  {"skiing": 0.3, "glaciers": 0.25, "snowshoeing": 0.2, "winter-nature": 0.2},
    "brown_sand":  {"sandy-beaches": 0.3, "ancient-ruins": 0.2, "historical-sites": 0.15},
    "orange_warm": {"local-cuisine": 0.2, "street-food": 0.2, "local-festivals": 0.15},
    "yellow":      {"sandy-beaches": 0.2, "photography-landscapes": 0.15},
    "dark":        {"nightlife-social": 0.25, "bar-scene": 0.2, "clubbing": 0.15},
    "colorful":    {"street-art": 0.2, "local-festivals": 0.25, "arts-museums": 0.15},
}

SEASON_PROMPTS = {
    "spring": "spring season blooming flowers fresh green leaves mild weather",
    "summer": "summer season bright sun lush green vegetation warm beach",
    "autumn": "autumn fall season orange red yellow leaves foliage",
    "winter": "winter season snow ice bare trees cold freezing",
}

SEASON_TAG_BOOSTS = {
    "summer": {"sandy-beaches": 0.2, "swimming": 0.15, "hiking": 0.1, "sailing": 0.1},
    "winter": {"skiing": 0.25, "winter-nature": 0.2, "snowshoeing": 0.15},
    "spring": {"cycling-biking": 0.15, "hiking": 0.15, "photography-landscapes": 0.1},
    "autumn": {"hiking": 0.2, "wine-vineyards": 0.15, "photography-landscapes": 0.15},
}


class CLIPService:
    _instance = None
    _model = None
    _processor = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        self._loaded = False

    def is_loaded(self) -> bool:
        return self._loaded

    def _load_model(self):
        """Încarcă modelul CLIP lazily — doar când e nevoie prima dată."""
        if self._loaded:
            return
        logger.info("Se încarcă modelul CLIP... (prima dată durează ~30 secunde)")
        self._model = CLIPModel.from_pretrained("openai/clip-vit-large-patch14")
        self._processor = CLIPProcessor.from_pretrained("openai/clip-vit-large-patch14")
        self._model.eval()
        self._loaded = True
        logger.info("Model CLIP încărcat cu succes!")

    def tag_image_from_url(self, image_url: str, top_k: int = 8) -> dict[str, float]:
        """
        Primește URL-ul unei imagini și returnează top_k taguri cu scoruri de confidență.
        """
        self._load_model()

        try:
            response = requests.get(image_url, timeout=10)
            image = Image.open(io.BytesIO(response.content)).convert("RGB")
            return self._classify_image(image, top_k)
        except Exception as e:
            logger.error(f"Eroare la procesarea imaginii {image_url}: {e}")
            return {}

    def tag_image_from_bytes(self, image_bytes: bytes, top_k: int = 8) -> dict[str, float]:
        """
        Primește bytes ai unei imagini și returnează top_k taguri.
        """
        self._load_model()

        try:
            image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
            return self._classify_image(image, top_k)
        except Exception as e:
            logger.error(f"Eroare la procesarea imaginii din bytes: {e}")
            return {}

    def _classify_image(self, image: Image.Image, top_k: int) -> dict[str, float]:
        """
        Clasifică o imagine față de toate tagurile noastre folosind CLIP.
        Returnează scoruri cosine similarity brute în intervalul tipic [0.15, 0.40]
        pentru CLIP-ViT-L/14 pe perechi text-imagine pozitive.

        Implementare: extragem embedding-urile de imagine și text separat, le normalizăm
        L2, apoi calculăm produsul scalar = cosine similarity (ambele vectori sunt deja
        unit-norm după normalizare).

        NU se aplică softmax și NU se normalizează prin max.
        - softmax(dim=0) pe 60 taguri distribuie 100% probabilitate pe toți candidații,
          colapsând diferențele reale de similaritate (media per tag = 1/60 ≈ 0.016).
        - divide-by-max forța tag-ul de top la 1.0 indiferent de confidența reală,
          făcând imposibilă comparația între imagini diferite.

        Scorurile brute cosine păstrează magnitudinea semnalului:
          0.35 pe o imagine și 0.35 pe alta = același nivel de certitudine.
          Cu softmax+max-norm, ambele apăreau ca 1.0 dar din distribuții complet diferite.
        """
        tags = [t for t in TAG_PROMPTS.keys() if t not in CLIP_EXCLUDED_TAGS]
        texts = [TAG_PROMPTS[tag] for tag in tags]

        inputs = self._processor(
            text=texts,
            images=image,
            return_tensors="pt",
            padding=True,
            truncation=True,
        )

        with torch.no_grad():
            outputs = self._model(**inputs)
            # logits_per_image = cosine_similarity(image, text) * logit_scale
            # logit_scale e un parametru learnat al modelului (~100 pentru CLIP-ViT-L/14)
            # Împărțind la logit_scale recuperăm cosine similarity-ul brut în [-1, 1].
            # Abordare mai robustă decât get_image_features() care poate returna
            # BaseModelOutputWithPooling în unele versiuni de transformers.
            logit_scale = self._model.logit_scale.exp()
            similarities = outputs.logits_per_image[0] / logit_scale

        # Scoruri brute cosine — fără softmax, fără normalizare prin max
        tag_scores = {
            tag: float(similarities[i])
            for i, tag in enumerate(tags)
        }

        # Returnăm top_k sortate descrescător; filtrarea finală în scriptul de tagging
        sorted_tags = sorted(tag_scores.items(), key=lambda x: x[1], reverse=True)
        return dict(sorted_tags[:top_k])

    def analyze_scene(self, image_bytes: bytes) -> dict:
        """Clasifică scena imaginii pe dimensiuni binare (indoor/outdoor, urban/natural etc.)."""
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        scenes = list(SCENE_PROMPTS.keys())
        texts = [SCENE_PROMPTS[s] for s in scenes]

        inputs = self._processor(
            text=texts, images=image,
            return_tensors="pt", padding=True
        )
        with torch.no_grad():
            outputs = self._model(**inputs)
            logit_scale = self._model.logit_scale.exp()
            similarities = (outputs.logits_per_image[0] / logit_scale).cpu()

        scores = {scenes[i]: float(similarities[i]) for i in range(len(scenes))}

        return {
            "scores": scores,
            "setting": "indoor" if scores["indoor"] > scores["outdoor"] else "outdoor",
            "environment": "urban" if scores["urban"] > scores["natural"] else "natural",
            "crowding": "crowded" if scores["crowded"] > scores["peaceful"] else "peaceful",
            "time_of_day": "night" if scores["nighttime"] > scores["daytime"] else "day",
            "has_landmark": scores["landmark"] > 0.22,
            "has_food": scores["food"] > 0.22,
            "has_beach": scores["beach"] > 0.22,
            "has_mountain": scores["mountain"] > 0.22,
        }

    def extract_dominant_colors(self, image_bytes: bytes, n_colors: int = 5) -> dict:
        """Extrage culorile dominante prin KMeans și le mapează la boost-uri de preferință."""
        from sklearn.cluster import KMeans

        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        image = image.resize((100, 100))
        pixels = np.array(image).reshape(-1, 3).astype(float)

        kmeans = KMeans(n_clusters=n_colors, random_state=42, n_init=10)
        kmeans.fit(pixels)

        colors = kmeans.cluster_centers_.astype(int)
        percentages = np.bincount(kmeans.labels_) / len(kmeans.labels_)

        color_results = []
        preference_boosts: dict = {}

        for color, pct in zip(colors, percentages):
            r, g, b = color
            h, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
            hue = h * 360

            if v < 0.2:
                category = "dark"
            elif s < 0.15:
                category = "white_grey"
            elif 200 <= hue <= 260:
                category = "blue_deep" if s > 0.5 else "blue_light"
            elif 80 <= hue <= 160:
                category = "green_dark" if v < 0.5 else "green_light"
            elif 20 <= hue <= 45:
                category = "brown_sand"
            elif 45 <= hue <= 80:
                category = "yellow"
            elif 0 <= hue <= 20 or hue >= 340:
                category = "orange_warm"
            else:
                category = "colorful"

            color_results.append({
                "rgb": [int(r), int(g), int(b)],
                "percentage": round(float(pct), 3),
                "category": category,
            })

            if category in COLOR_TO_TAGS:
                for tag, boost in COLOR_TO_TAGS[category].items():
                    preference_boosts[tag] = (
                        preference_boosts.get(tag, 0) + boost * float(pct)
                    )

        return {
            "dominant_colors": sorted(color_results, key=lambda x: -x["percentage"]),
            "preference_boosts": preference_boosts,
        }

    def estimate_season(self, image_bytes: bytes) -> dict:
        """Estimează sezonul dominant din imagine folosind CLIP."""
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        seasons = list(SEASON_PROMPTS.keys())
        texts = [SEASON_PROMPTS[s] for s in seasons]

        inputs = self._processor(
            text=texts, images=image,
            return_tensors="pt", padding=True
        )
        with torch.no_grad():
            outputs = self._model(**inputs)
            logit_scale = self._model.logit_scale.exp()
            similarities = (outputs.logits_per_image[0] / logit_scale).cpu()

        season_scores = {seasons[i]: float(similarities[i]) for i in range(len(seasons))}
        dominant = max(season_scores, key=season_scores.get)

        return {
            "season_scores": season_scores,
            "dominant_season": dominant,
            "tag_boosts": SEASON_TAG_BOOSTS.get(dominant, {}),
        }


# Singleton global
clip_service = CLIPService.get_instance()