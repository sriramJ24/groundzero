import os
import numpy as np,cv2,json,os,base64,glob
from scipy import ndimage
W=os.environ.get('BLT_WORK','/tmp/blt_work/'); OUT=W+'site/data/'; os.makedirs(OUT,exist_ok=True)
g=np.load(W+'geo.npz'); U=g['U']; N=g['N']
D=os.path.join(os.path.dirname(os.path.abspath(__file__)),'../../viewer/demo-data/blt_sample/')
GZ0=0.15; GEO=0.02; STEP=0.05; k=int(STEP/GEO)
metas=[json.load(open(f)) for f in sorted(glob.glob(D+'meta/*.json'))]
P=np.array([m['pose_map']['position'][:2] for m in metas])
row_n=float((np.median(g['A_n'])+np.median(g['B_n']))/2)
faces=[];scene={}
TILE=2048
for side in 'AB':
    n=g[f'{side}_n']; sh=g[f'{side}_shown']; s0=float(g[f'{side}_s0'])
    nz,ns=n.shape
    nd=n[::k,::k]-row_n; shd=sh[::k,::k]
    q=np.clip(np.round(nd/0.005)+128,0,255).astype(np.uint8)
    tex=cv2.imread(W+f'tex_{side}.jpg'); al=cv2.imread(W+f'alpha_{side}.png',0)
    rgba=np.dstack([tex,al])
    tiles=[]
    for t0 in range(0,tex.shape[1],TILE):
        t=rgba[:,t0:t0+TILE]
        fn=f'face{side}_{t0//TILE}'
        cv2.imwrite(OUT+fn+'.webp',t,[cv2.IMWRITE_WEBP_QUALITY,85])
        tiles.append(dict(file=fn+'.webp',s0=s0+t0*0.0025,s1=s0+(t0+t.shape[1])*0.0025))
    faces.append(dict(side=side,s0=s0,step=STEP,z0=GZ0,cols=nd.shape[1],rows=nd.shape[0],
        offset_b64=base64.b64encode(q[::-1].tobytes()).decode(),shown_b64=base64.b64encode(np.ones_like(shd[::-1],np.uint8).tobytes()).decode(),
        offset_scale=0.005,tiles=tiles,z1=GZ0+n.shape[0]*GEO))
track=[[round(float(p@U),3),round(float(p@N)-row_n,3)] for p in P]
scene=dict(row_n=row_n,faces=faces,track=track,frames=len(metas))
json.dump(scene,open(OUT+'scene.json','w'))
print(sum(os.path.getsize(OUT+f) for f in os.listdir(OUT))/1e6,'MB')
