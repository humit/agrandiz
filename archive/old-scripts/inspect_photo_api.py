import osxphotos
from pprint import pprint

photosdb = osxphotos.PhotosDB()
photos = photosdb.photos()

print("count:", len(photos))

# Önce lokal erişilebilir bir fotoğraf bulmaya çalış
p = next((x for x in photos if not getattr(x, "ismissing", False)), photos[0])

print("type:", type(p))
print("uuid:", getattr(p, "uuid", None))
print("filename:", getattr(p, "original_filename", None))
print("date:", getattr(p, "date", None))
print("favorite:", getattr(p, "favorite", None))
print("ismissing:", getattr(p, "ismissing", None))
print("path:", getattr(p, "path", None))
print("path_edited:", getattr(p, "path_edited", None))
print("persons:", getattr(p, "persons", None))
print("albums:", getattr(p, "albums", None))
print("labels:", getattr(p, "labels", None))
print("keywords:", getattr(p, "keywords", None))
print("media_type:", getattr(p, "media_type", None))
print("uti:", getattr(p, "uti", None))
print("height:", getattr(p, "height", None))
print("width:", getattr(p, "width", None))
print("description:", getattr(p, "description", None))
print("title:", getattr(p, "title", None))
print("place:", getattr(p, "place", None))
print("moment:", getattr(p, "moment", None))

print("\\nKnown non-callable public attrs containing useful words:")
interesting = [
    "path", "file", "missing", "cloud", "label", "score", "caption",
    "width", "height", "size", "uti", "media", "album", "person",
    "favorite", "screenshot", "burst", "live", "date", "moment", "place",
    "search", "source", "orientation", "dimension"
]

for name in dir(p):
    if name.startswith("_"):
        continue
    if not any(word in name.lower() for word in interesting):
        continue
    try:
        value = getattr(p, name)
    except Exception as e:
        value = f"<ERR {type(e).__name__}: {e}>"
    if callable(value):
        continue
    print(f"{name}: {repr(value)[:300]}")

score = getattr(p, "score", None)
print("\\nscore object:", score)
if score:
    print("score attrs:")
    for name in dir(score):
        if name.startswith("_"):
            continue
        try:
            value = getattr(score, name)
        except Exception as e:
            value = f"<ERR {type(e).__name__}: {e}>"
        if not callable(value):
            print(f"  {name}: {value}")

print("\\nAll public attrs snapshot:")
attrs = []
for name in dir(p):
    if name.startswith("_"):
        continue
    try:
        value = getattr(p, name)
    except Exception:
        continue
    if callable(value):
        continue
    attrs.append(name)

pprint(attrs)
