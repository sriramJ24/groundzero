import os
"""Per-frame depth-mesh export: each frame contributes the central slice of its own photo, draped on its own depth."""
import numpy as np,cv2,json,os,glob,sys
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
from pts import qmat,Rbc,tbc,D,cam
W=os.environ.get('BLT_WORK','/tmp/blt_work/'); OUT=W+'site2/data/'; os.makedirs(OUT+'f',exist_ok=True)
g=np.load(W+'geo.npz'); U=g['U']; N=g['N']
Kd=np.array(cam['K_depth_scaled']).reshape(3,3)
metas=[json.load(open(f)) for f in sorted(glob.glob(D+'meta/*.json'))]
row_n=float((np.median(g['A_n'])+np.median(g['B_n']))/2)
FR=list(range(5,93))+list(range(114,206))
S=np.array([np.array(metas[i]['pose_map']['position'][:2])@U for i in FR]); sMid=float((S.min()+S.max())/2)
M=np.array([[U[0],U[1],0],[0,0,1],[N[0],N[1],0]])  # world -> viewer axes
mo=np.array([-sMid,0,-row_n])
frames=[]
for i in FR:
    m=metas[i]; p=m['pose_map']; Rwb=qmat(p['orientation_xyzw']); twb=np.array(p['position'])
    R=M@Rwb@Rbc; t=M@(Rwb@tbc+twb)+mo
    d=cv2.imread(D+f'depth/{i:04d}.png',-1).astype(np.float32)/1000
    v=d[(d>0.2)&(d<3)]
    dm=float(np.median(v[v<1.6])) if (v<1.6).sum()>500 else None
    if dm is None: continue
    hw=int(np.ceil(0.30/dm*Kd[0,0]))
    c0=max(0,int(Kd[0,2])-hw); c1=min(320,int(Kd[0,2])+hw)
    dc=d[:,c0:c1].copy()
    bad=(dc<=0.2)|(dc>dm+0.4)|(dc>2.84)
    q=np.clip(np.round((dc-0.3)/0.01),1,255).astype(np.uint8); q[bad]=0
    cv2.imwrite(OUT+f'f/{i:04d}_d.png',q)
    rgb=cv2.imread(D+f'rgb/{i:04d}.jpg')[:,c0*4:c1*4]
    cv2.imwrite(OUT+f'f/{i:04d}.webp',rgb,[cv2.IMWRITE_WEBP_QUALITY,78])
    frames.append(dict(id=f'{i:04d}',c0=c0,w=c1-c0,R=np.round(R,6).tolist(),t=np.round(t,4).tolist(),side='A' if i<100 else 'B',
                       s=round(float(np.array(p['position'][:2])@U-sMid),3),captured=m['timestamp_unix'],gps=[m['gps']['lat'],m['gps']['lon']]))
track=[[round(float(np.array(m['pose_map']['position'][:2])@U-sMid),3),round(float(np.array(m['pose_map']['position'][:2])@N-row_n),3)] for m in metas]
json.dump(dict(K=Kd.tolist(),depth_h=180,depth_q=dict(offset=0.3,step=0.01),frames=frames,track=track,s_range=[float(S.min()-sMid),float(S.max()-sMid)]),open(OUT+'scene.json','w'))
tot=sum(os.path.getsize(os.path.join(dp,f)) for dp,_,fs in os.walk(OUT) for f in fs)
print(len(frames),'frames',tot/1e6,'MB')
