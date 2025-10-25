import os
from PIL import Image
from tqdm import tqdm

# Dossier source : ton dossier "about"
SOURCE_DIR = r"core/static/images/hero"
# Dossier de sortie : les images compressées WebP
OUTPUT_DIR = r"core/static/images/hero_webp"

# Crée le dossier de sortie s'il n'existe pas
os.makedirs(OUTPUT_DIR, exist_ok=True)

def convert_and_compress_image(input_path, output_path):
    """Convertit une image en WebP avec compression (qualité élevée)"""
    try:
        img = Image.open(input_path).convert("RGB")
        img.save(output_path, "WEBP", quality=85, method=6)
        return True
    except Exception as e:
        print(f"❌ Erreur avec {input_path}: {e}")
        return False

# Extensions d'images à traiter
extensions = (".jpg", ".jpeg", ".png", ".bmp")

# Lister les fichiers
all_images = [f for f in os.listdir(SOURCE_DIR) if f.lower().endswith(extensions)]

print(f"🔍 {len(all_images)} images trouvées dans {SOURCE_DIR}")
for filename in tqdm(all_images, desc="Compression WebP"):
    input_path = os.path.join(SOURCE_DIR, filename)
    name, _ = os.path.splitext(filename)
    output_path = os.path.join(OUTPUT_DIR, name + ".webp")
    convert_and_compress_image(input_path, output_path)

print("\n✅ Conversion terminée avec succès !")
print(f"📂 Images WebP disponibles dans : {OUTPUT_DIR}")
