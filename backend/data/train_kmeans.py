import os
from urllib.parse import urlparse
from dotenv import load_dotenv
import psycopg2
import psycopg2.extras
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.preprocessing import MultiLabelBinarizer

# Încarcă .env din folderul backend/ (un nivel sus față de data/)
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

db_url = os.getenv("DATABASE_URL")
if not db_url:
    raise RuntimeError("DATABASE_URL lipsește din .env")

parsed = urlparse(db_url)
DB_CONFIG = {
    "host": parsed.hostname,
    "port": parsed.port,
    "database": parsed.path.lstrip("/"),
    "user": parsed.username,
    "password": parsed.password,
}
K = 4  # număr clustere per nivel

# ============================================================
# 1. CONECTARE + CITIRE DATE
# ============================================================
def get_conn():
    return psycopg2.connect(**DB_CONFIG)

def load_destinations():
    conn = get_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute("SELECT id, name, country, cluster, tags FROM destinations ORDER BY id;")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows

# ============================================================
# 2. VECTORIZARE TAGURI
# ============================================================
def vectorize(rows):
    tag_lists = [r["tags"].split(",") for r in rows]
    mlb = MultiLabelBinarizer()
    X = mlb.fit_transform(tag_lists)
    return X, mlb.classes_

# ============================================================
# 3. SETUP TABELE DB
# ============================================================
CREATE_CLUSTERS_TABLE = """
CREATE TABLE IF NOT EXISTS clusters (
    id SERIAL PRIMARY KEY,
    level INTEGER NOT NULL,
    cluster_label VARCHAR(20) NOT NULL,
    parent_cluster_label VARCHAR(20),
    top_tags TEXT NOT NULL,
    representative_dest_id INTEGER REFERENCES destinations(id),
    representative_dest_name VARCHAR(255),
    dest_count INTEGER DEFAULT 0
);
"""

ADD_COLUMNS = """
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='destinations' AND column_name='cluster_l1') THEN
        ALTER TABLE destinations ADD COLUMN cluster_l1 VARCHAR(20);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='destinations' AND column_name='cluster_l2') THEN
        ALTER TABLE destinations ADD COLUMN cluster_l2 VARCHAR(20);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='destinations' AND column_name='cluster_l3') THEN
        ALTER TABLE destinations ADD COLUMN cluster_l3 VARCHAR(20);
    END IF;
END$$;
"""

def setup_db():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DROP TABLE IF EXISTS clusters;")
    cur.execute(CREATE_CLUSTERS_TABLE)
    cur.execute(ADD_COLUMNS)
    cur.execute("UPDATE destinations SET cluster_l1=NULL, cluster_l2=NULL, cluster_l3=NULL;")
    conn.commit()
    cur.close()
    conn.close()
    print("✅ Tabele pregătite")

# ============================================================
# 4. UTILITAR: top taguri din centroid
# ============================================================
def top_tags_from_centroid(centroid, tag_names, n=5):
    top_idx = np.argsort(centroid)[::-1][:n]
    return [tag_names[i] for i in top_idx if centroid[i] > 0.01]

# ============================================================
# 5. UTILITAR: destinația cea mai apropiată de centroid
# ============================================================
def representative_dest(X_subset, centroid, subset_rows):
    dists = np.linalg.norm(X_subset - centroid, axis=1)
    closest_idx = np.argmin(dists)
    return subset_rows[closest_idx]

# ============================================================
# 6. RULARE K-MEANS IERARHIC
# ============================================================
def run_kmeans(rows, X, tag_names):
    ids = [r["id"] for r in rows]
    
    # Dict pentru update final: dest_id -> (l1, l2, l3)
    assignments = {r["id"]: {"l1": None, "l2": None, "l3": None} for r in rows}
    
    clusters_to_insert = []

    # --- NIVEL 1 ---
    print(f"\n🔵 Nivel 1: K-Means k={K} pe {len(rows)} destinații")
    km1 = KMeans(n_clusters=K, random_state=42, n_init=10)
    labels1 = km1.fit_predict(X)

    for c1 in range(K):
        mask1 = labels1 == c1
        subset1_rows = [rows[i] for i in range(len(rows)) if mask1[i]]
        subset1_X = X[mask1]
        centroid1 = km1.cluster_centers_[c1]
        top1 = top_tags_from_centroid(centroid1, tag_names)
        rep1 = representative_dest(subset1_X, centroid1, subset1_rows)
        label1 = f"L1-{c1}"

        clusters_to_insert.append({
            "level": 1,
            "label": label1,
            "parent": None,
            "top_tags": ",".join(top1),
            "rep_id": rep1["id"],
            "rep_name": rep1["name"],
            "count": len(subset1_rows)
        })

        for r in subset1_rows:
            assignments[r["id"]]["l1"] = label1

        print(f"  {label1}: {len(subset1_rows)} dest | top tags: {top1[:3]}")

        # --- NIVEL 2 ---
        if len(subset1_rows) < K:
            print(f"    ⚠️  Sub-set prea mic pentru nivel 2, skip")
            continue

        k2 = min(K, len(subset1_rows))
        km2 = KMeans(n_clusters=k2, random_state=42, n_init=10)
        labels2 = km2.fit_predict(subset1_X)

        for c2 in range(k2):
            mask2 = labels2 == c2
            subset2_rows = [subset1_rows[i] for i in range(len(subset1_rows)) if mask2[i]]
            subset2_X = subset1_X[mask2]
            centroid2 = km2.cluster_centers_[c2]
            top2 = top_tags_from_centroid(centroid2, tag_names)
            rep2 = representative_dest(subset2_X, centroid2, subset2_rows)
            label2 = f"L2-{c1}-{c2}"

            clusters_to_insert.append({
                "level": 2,
                "label": label2,
                "parent": label1,
                "top_tags": ",".join(top2),
                "rep_id": rep2["id"],
                "rep_name": rep2["name"],
                "count": len(subset2_rows)
            })

            for r in subset2_rows:
                assignments[r["id"]]["l2"] = label2

            # --- NIVEL 3 ---
            if len(subset2_rows) < K:
                continue

            k3 = min(K, len(subset2_rows))
            km3 = KMeans(n_clusters=k3, random_state=42, n_init=10)
            labels3 = km3.fit_predict(subset2_X)

            for c3 in range(k3):
                mask3 = labels3 == c3
                subset3_rows = [subset2_rows[i] for i in range(len(subset2_rows)) if mask3[i]]
                subset3_X = subset2_X[mask3]
                centroid3 = km3.cluster_centers_[c3]
                top3 = top_tags_from_centroid(centroid3, tag_names)
                rep3 = representative_dest(subset3_X, centroid3, subset3_rows)
                label3 = f"L3-{c1}-{c2}-{c3}"

                clusters_to_insert.append({
                    "level": 3,
                    "label": label3,
                    "parent": label2,
                    "top_tags": ",".join(top3),
                    "rep_id": rep3["id"],
                    "rep_name": rep3["name"],
                    "count": len(subset3_rows)
                })

                for r in subset3_rows:
                    assignments[r["id"]]["l3"] = label3

    return clusters_to_insert, assignments

# ============================================================
# 7. SALVARE ÎN DB
# ============================================================
def save_to_db(clusters_to_insert, assignments):
    conn = get_conn()
    cur = conn.cursor()

    # Inserează clustere
    print(f"\n💾 Salvez {len(clusters_to_insert)} clustere în DB...")
    for c in clusters_to_insert:
        cur.execute("""
            INSERT INTO clusters (level, cluster_label, parent_cluster_label, top_tags,
                                  representative_dest_id, representative_dest_name, dest_count)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (c["level"], c["label"], c["parent"], c["top_tags"],
              c["rep_id"], c["rep_name"], c["count"]))

    # Update destinations cu cluster labels
    print(f"💾 Salvez asignările în destinations...")
    for dest_id, asgn in assignments.items():
        cur.execute("""
            UPDATE destinations
            SET cluster_l1 = %s, cluster_l2 = %s, cluster_l3 = %s
            WHERE id = %s
        """, (asgn["l1"], asgn["l2"], asgn["l3"], dest_id))

    conn.commit()
    cur.close()
    conn.close()
    print("✅ Salvat în DB")

# ============================================================
# 8. STATISTICI FINALE
# ============================================================
def print_stats(clusters_to_insert):
    l1 = [c for c in clusters_to_insert if c["level"] == 1]
    l2 = [c for c in clusters_to_insert if c["level"] == 2]
    l3 = [c for c in clusters_to_insert if c["level"] == 3]

    print(f"\n📊 REZULTATE FINALE:")
    print(f"   Nivel 1: {len(l1)} clustere")
    print(f"   Nivel 2: {len(l2)} sub-clustere")
    print(f"   Nivel 3: {len(l3)} sub-sub-clustere")
    print(f"\n🎯 Clustere nivel 1 (imaginile din Quiz Runda 1):")
    for c in l1:
        print(f"   {c['label']}: {c['count']} dest | rep: {c['rep_name']} | tags: {c['top_tags']}")

# ============================================================
# MAIN
# ============================================================
if __name__ == "__main__":
    print("🚀 TripCraft — Training K-Means ierarhic")

    print("\n📖 Citesc destinații din DB...")
    rows = load_destinations()
    print(f"   {len(rows)} destinații încărcate")

    print("\n🔢 Vectorizez tagurile...")
    X, tag_names = vectorize(rows)
    print(f"   Matrice: {X.shape[0]} destinații × {X.shape[1]} taguri")

    setup_db()

    clusters_to_insert, assignments = run_kmeans(rows, X, tag_names)

    save_to_db(clusters_to_insert, assignments)

    print_stats(clusters_to_insert)

    print("\n✅ DONE! Acum poți construi quiz-ul și recomandările pe clustere.")        