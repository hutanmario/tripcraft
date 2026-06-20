"""
kmeans_quiz_images.py
Rulează K-Means pe embeddings CLIP ale imaginilor de quiz.
Produce clustere vizuale și salvează rezultatele în quiz_clusters.json.
"""

import os
import json
import numpy as np
from PIL import Image
from sklearn.cluster import KMeans
from sklearn.preprocessing import normalize
import torch
from transformers import CLIPProcessor, CLIPModel

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
IMAGES_DIR = os.path.join(BASE_DIR, "..", "static", "quiz-images")
MANIFEST_PATH = os.path.join(IMAGES_DIR, "manifest.json")
OUTPUT_PATH = os.path.join(IMAGES_DIR, "quiz_clusters.json")

N_CLUSTERS_LEVEL1 = 6
N_CLUSTERS_LEVEL2 = 3


def load_clip():
    print("Se încarcă modelul CLIP...")
    model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32")
    processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")
    model.eval()
    print("CLIP încărcat!")
    return model, processor


def get_image_embedding(model, processor, image_path: str) -> np.ndarray:
    """Generează embedding CLIP pentru o imagine."""
    image = Image.open(image_path).convert("RGB")
    inputs = processor(images=image, return_tensors="pt")
    with torch.no_grad():
        outputs = model.vision_model(**inputs)
        features = outputs.pooler_output
    return features.detach().cpu().numpy()[0]


def find_representative_image(embeddings: np.ndarray, centroid: np.ndarray, indices: list) -> int:
    """Găsește imaginea cea mai apropiată de centroidul unui cluster."""
    distances = np.linalg.norm(embeddings[indices] - centroid, axis=1)
    return indices[np.argmin(distances)]


def main():
    # Încarcă manifestul
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    # Colectează toate imaginile
    all_images = []
    for category, images in manifest.items():
        for img in images:
            all_images.append({
                "category": category,
                "path": os.path.join(IMAGES_DIR, category, img["filename"]),
                "web_path": img["path"],
                "filename": img["filename"],
                "query": img["query"],
            })

    print(f"Total imagini: {len(all_images)}")

    # Încarcă CLIP și generează embeddings
    model, processor = load_clip()

    print("Generez embeddings CLIP pentru toate imaginile...")
    embeddings = []
    valid_images = []

    for i, img_data in enumerate(all_images):
        print(f"  [{i+1}/{len(all_images)}] {img_data['filename']}...", end=" ")
        try:
            emb = get_image_embedding(model, processor, img_data["path"])
            embeddings.append(emb)
            valid_images.append(img_data)
            print("✓")
        except Exception as e:
            print(f"✗ {e}")

    embeddings = np.array(embeddings)
    embeddings_normalized = normalize(embeddings)

    print(f"\nEmbeddings generate: {len(embeddings)} × {embeddings.shape[1]}D")

    # ─── Level 1: K-Means cu N_CLUSTERS_LEVEL1 clustere ───────────────────────
    print(f"\nRulez K-Means Level 1 ({N_CLUSTERS_LEVEL1} clustere)...")
    kmeans_l1 = KMeans(n_clusters=N_CLUSTERS_LEVEL1, random_state=42, n_init=10)
    labels_l1 = kmeans_l1.fit_predict(embeddings_normalized)

    level1_clusters = {}
    for cluster_id in range(N_CLUSTERS_LEVEL1):
        cluster_indices = [i for i, l in enumerate(labels_l1) if l == cluster_id]
        centroid = kmeans_l1.cluster_centers_[cluster_id]
        representative_idx = find_representative_image(embeddings_normalized, centroid, cluster_indices)
        representative = valid_images[representative_idx]

        # Determină numele clusterului pe baza categoriei dominante
        categories_in_cluster = [valid_images[i]["category"] for i in cluster_indices]
        dominant_category = max(set(categories_in_cluster), key=categories_in_cluster.count)

        level1_clusters[str(cluster_id)] = {
            "cluster_id": cluster_id,
            "dominant_category": dominant_category,
            "size": len(cluster_indices),
            "representative": {
                "path": representative["web_path"],
                "category": representative["category"],
                "query": representative["query"],
            },
            "images": [
                {
                    "path": valid_images[i]["web_path"],
                    "category": valid_images[i]["category"],
                    "query": valid_images[i]["query"],
                }
                for i in cluster_indices
            ],
        }

        print(f"  Cluster {cluster_id}: {dominant_category} ({len(cluster_indices)} imagini)")

    # ─── Level 2: Sub-clustere per cluster Level 1 ────────────────────────────
    print(f"\nRulez K-Means Level 2 ({N_CLUSTERS_LEVEL2} sub-clustere per cluster)...")

    for cluster_id_str, cluster_data in level1_clusters.items():
        cluster_id = int(cluster_id_str)
        cluster_indices = [i for i, l in enumerate(labels_l1) if l == cluster_id]

        if len(cluster_indices) < N_CLUSTERS_LEVEL2:
            # Prea puține imagini pentru sub-clustering
            cluster_data["sub_clusters"] = None
            continue

        cluster_embeddings = embeddings_normalized[cluster_indices]
        kmeans_l2 = KMeans(n_clusters=N_CLUSTERS_LEVEL2, random_state=42, n_init=10)
        labels_l2 = kmeans_l2.fit_predict(cluster_embeddings)

        sub_clusters = {}
        for sub_id in range(N_CLUSTERS_LEVEL2):
            sub_indices_local = [i for i, l in enumerate(labels_l2) if l == sub_id]
            sub_indices_global = [cluster_indices[i] for i in sub_indices_local]
            centroid = kmeans_l2.cluster_centers_[sub_id]
            rep_local = find_representative_image(cluster_embeddings, centroid, sub_indices_local)
            rep_global = cluster_indices[rep_local]
            representative = valid_images[rep_global]

            sub_clusters[str(sub_id)] = {
                "sub_cluster_id": sub_id,
                "size": len(sub_indices_global),
                "representative": {
                    "path": representative["web_path"],
                    "category": representative["category"],
                    "query": representative["query"],
                },
                "images": [
                    {
                        "path": valid_images[i]["web_path"],
                        "category": valid_images[i]["category"],
                        "query": valid_images[i]["query"],
                    }
                    for i in sub_indices_global
                ],
            }

        cluster_data["sub_clusters"] = sub_clusters
        print(f"  Cluster {cluster_id} ({cluster_data['dominant_category']}): {N_CLUSTERS_LEVEL2} sub-clustere")

    # ─── Salvează rezultatele ──────────────────────────────────────────────────
    output = {
        "total_images": len(valid_images),
        "n_clusters_level1": N_CLUSTERS_LEVEL1,
        "n_clusters_level2": N_CLUSTERS_LEVEL2,
        "level1": level1_clusters,
    }

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"\n✅ Done! Clustere salvate în: {OUTPUT_PATH}")
    print(f"   Level 1: {N_CLUSTERS_LEVEL1} clustere")
    print(f"   Level 2: {N_CLUSTERS_LEVEL2} sub-clustere per cluster")


if __name__ == "__main__":
    main()