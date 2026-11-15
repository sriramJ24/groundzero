import ssl, certifi
import urllib.parse, urllib.request, io, random, glob
from PIL import Image
OUT="/Users/sriramjoshi/Code/Hackathons/GroundZero/groundzero/frontend/public/demo/images/"
cls={"healthy":"Corn_(maize)___healthy","blight":"Corn_(maize)___Northern_Leaf_Blight","rust":"Corn_(maize)___Common_rust_","gray":"Corn_(maize)___Cercospora_leaf_spot Gray_leaf_spot"}
lst={k:open("cache/list_"+"".join(c if c.isalnum() else "_" for c in v)+".txt").read().split("\n") for k,v in cls.items()}
lst={k:[x for x in v if x.lower().endswith(".jpg")] for k,v in lst.items()}
random.seed(7)
plan=[("healthy",f"healthy_{i:02d}.jpg") for i in range(1,9)]
dis=["blight","rust","gray","blight","rust","gray","blight","rust"]
plan+= [(k,f"discoloration_{i+1:02d}.jpg") for i,k in enumerate(dis)]
rows=[]
for k,name in plan:
    f=random.choice(lst[k]); lst[k].remove(f)
    url="https://raw.githubusercontent.com/spMohanty/PlantVillage-Dataset/master/raw/color/"+urllib.parse.quote(cls[k])+"/"+urllib.parse.quote(f)
    im=Image.open(io.BytesIO(urllib.request.urlopen(url,timeout=30,context=ssl.create_default_context(cafile=certifi.where())).read())).convert("RGB")
    w,h=im.size; t=320/240
    if w/h>t: nw=int(h*t); im=im.crop(((w-nw)//2,0,(w-nw)//2+nw,h))
    else: nh=int(w/t); im=im.crop((0,(h-nh)//2,w,(h-nh)//2+nh))
    im=im.resize((320,240),Image.LANCZOS); im.save(OUT+name,"JPEG",quality=82)
    rows.append(f"{name}  <-  {f}  (class: {cls[k]})")
open(OUT+"images_plantvillage_ATTRIBUTION.txt","w").write("""Maize leaf sample images: PlantVillage Dataset
Dataset: PlantVillage Dataset (raw/color), https://github.com/spMohanty/PlantVillage-Dataset
Paper: Hughes, D. P. & Salathe, M. (2015). An open access repository of images on plant health to enable the development of mobile disease diagnostics. arXiv:1511.08060.
Also cited by the repo: Mohanty, Hughes & Salathe (2016), Frontiers in Plant Science 7:1419, doi:10.3389/fpls.2016.01419.
Licence: CC BY-SA 3.0 (cc-by-sa-3.0), as stated in the repo's README_HF.md metadata. The repo has no separate LICENSE file. Attribution required; derivatives must be shared under the same licence.
Modifications: each image centre-cropped to 4:3 and resized to 320x240, re-encoded as JPEG quality 82.

Output file  <-  original file name (class)
"""+"\n".join(rows)+"\n")
print("\n".join(rows))
