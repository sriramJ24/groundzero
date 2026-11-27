import os  # CORN_WORK: folder with flags.json and Day<day>_Corn/{transforms.json,sparse_pc.ply,images/}
import json,numpy as np,cv2
W=os.environ.get('CORN_WORK','work/corn/')
F=json.load(open(W+'flags.json')); P=json.load(open(W+'pick.json'))
X0,Y1,C=-10.0,9.0,0.5
out={}
for day,L in P.items():
    t=json.load(open(W+f'Day{day}_Corn/transforms.json'))
    fr={f['file_path']:f for f in t['frames']}
    K=np.array([[t['fl_x'],0,t['cx']],[0,t['fl_y'],t['cy']],[0,0,1]]); dist=np.array([t['k1'],t['k2'],t['p1'],t['p2'],t['k3']])
    flags={f['id']:f for f in F['dates'][day]['flags']}
    for p in L:
        f=flags[p['id']]; z=p['z']
        # outline of the union of cells, sampled densely so distortion bends it correctly
        cells=set(map(tuple,f['cells_rc'])); segs=[]
        for r,c in cells:
            x0=X0+c*C; y0=Y1-r*C
            if (r-1,c) not in cells: segs.append(((x0,y0),(x0+C,y0)))
            if (r+1,c) not in cells: segs.append(((x0,y0-C),(x0+C,y0-C)))
            if (r,c-1) not in cells: segs.append(((x0,y0),(x0,y0-C)))
            if (r,c+1) not in cells: segs.append(((x0+C,y0),(x0+C,y0-C)))
        ev=[]
        for view in ('oblique','nadir'):
            c=p[view]
            if not c: continue
            img=cv2.imread(W+f"Day{day}_Corn/{c['file']}")
            c2w=np.array(fr[c['file']]['transform_matrix'])@np.diag([1,-1,-1,1]); w2c=np.linalg.inv(c2w)
            rvec,_=cv2.Rodrigues(w2c[:3,:3]); tv=w2c[:3,3]
            allpts=[]
            for a,b in segs:
                s=np.linspace(0,1,9)[:,None]; pts=np.c_[np.array(a)+(np.array(b)-np.array(a))*s, np.full(9,z)]
                uv=cv2.projectPoints(pts,rvec,tv,K,dist)[0].reshape(-1,2); allpts.append(uv)
            A=np.vstack(allpts)
            # crop: 4 m x 4 m around the flag centre, projected
            sq=np.array([[f['x']+dx,f['y']+dy,z] for dx in (-2,2) for dy in (-2,2)])
            sqp=cv2.projectPoints(sq,rvec,tv,K,dist)[0].reshape(-1,2)
            u0,v0=np.floor(np.minimum(sqp.min(0),A.min(0)-60)).astype(int); u1,v1=np.ceil(np.maximum(sqp.max(0),A.max(0)+60)).astype(int)
            u0,v0=max(u0,0),max(v0,0); u1,v1=min(u1,img.shape[1]),min(v1,img.shape[0])
            crop=img[v0:v1,u0:u1].copy()
            sc=960/max(crop.shape[1],crop.shape[0]); crop=cv2.resize(crop,None,fx=sc,fy=sc,interpolation=cv2.INTER_AREA)
            for uv in allpts:
                q=((uv-[u0,v0])*sc).astype(np.int32)
                cv2.polylines(crop,[q],False,(0,0,0),5,cv2.LINE_AA); cv2.polylines(crop,[q],False,(0,215,255),2,cv2.LINE_AA)
            name=f"{p['id'].replace('-','_')}_{'angled' if view=='oblique' else 'down'}.jpg"
            cv2.imwrite(W+'ev/'+name,crop,[cv2.IMWRITE_JPEG_QUALITY,84])
            bb=((A.min(0)-[u0,v0])*sc).round().tolist()+((A.max(0)-[u0,v0])*sc).round().tolist()
            ev.append(dict(file='flags/ev/'+name,source=f"UAV3DCrop 2025 Day{day}_Corn {c['file']}",view='angled (45°)' if view=='oblique' else 'straight down',
                           camera_m=round(c['dist'],1),crop_px=[int(u0),int(v0),int(u1),int(v1)],box=bb))
        out[p['id']]=ev
        print(p['id'],[e['file'] for e in ev])
json.dump(out,open(W+'evidence.json','w'),indent=1)
