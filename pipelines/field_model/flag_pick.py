import os  # CORN_WORK: folder with flags.json and Day<day>_Corn/{transforms.json,sparse_pc.ply,images/}
import json,numpy as np,cv2
W=os.environ.get('CORN_WORK','work/corn/')
F=json.load(open(W+'flags.json'))
X0,Y1,C=-10.0,9.0,0.5
def ply(p):
    b=open(p,'rb').read(); i=b.index(b'end_header')+len(b'end_header'); i+= 2 if b[i:i+2]==b'\r\n' else 1
    dt=np.dtype([('x','<f4'),('y','<f4'),('z','<f4'),('r','u1'),('g','u1'),('b','u1')])
    return np.frombuffer(b[i:],dt)
out={}
for day in ('028','096'):
    t=json.load(open(W+f'Day{day}_Corn/transforms.json'))
    pc=ply(W+f'Day{day}_Corn/sparse_pc.ply'); P=np.c_[pc['x'],pc['y'],pc['z']]
    # sparse_pc frame vs transforms frame: check applied_transform
    K=np.array([[t['fl_x'],0,t['cx']],[0,t['fl_y'],t['cy']],[0,0,1]]); dist=np.array([t['k1'],t['k2'],t['p1'],t['p2'],t['k3']])
    flags=[f for f in F['dates'][day]['flags'] if f.get('crop')]
    res=[]
    for f in flags:
        near=np.hypot(P[:,0]-f['x'],P[:,1]-f['y'])<1.0
        z=float(np.median(P[near,2])) if near.sum()>5 else None
        # polygon corners of cells
        pts=[]
        for r,c in f['cells_rc']:
            x0=X0+c*C; y0=Y1-r*C
            pts+= [[x0,y0],[x0+C,y0],[x0,y0-C],[x0+C,y0-C]]
        pts=np.array(pts); ctr=np.array([f['x'],f['y'],z])
        cands=[]
        for fr in t['frames']:
            c2w=np.array(fr['transform_matrix'])@np.diag([1,-1,-1,1]); w2c=np.linalg.inv(c2w)
            pc_=w2c[:3,:3]@ctr+w2c[:3,3]
            if pc_[2]<=0: continue
            uv=K@pc_; u,v=uv[0]/uv[2],uv[1]/uv[2]
            if not (300<u<t['w']-300 and 300<v<t['h']-300): continue
            nad=c2w[2,2]  # camera z (opencv forward) world z component: -1 = straight down
            off=np.hypot(u-t['cx'],v-t['cy'])/t['w']
            cands.append(dict(file=fr['file_path'],nadir=c2w[:3,2][2]<-0.9,off=off,dist=float(pc_[2]),u=u,v=v))
        best_n=min([c for c in cands if c['nadir']],key=lambda c:c['off'],default=None)
        best_o=min([c for c in cands if not c['nadir']],key=lambda c:c['off']+0.02*c['dist'],default=None)
        res.append(dict(id=f['id'],kind=f['kind'],x=f['x'],y=f['y'],z=z,nadir=best_n,oblique=best_o,ncand=len(cands)))
        print(f['id'],f['kind'],'z=%.2f'%z if z is not None else z,len(cands),best_n and best_n['file'],best_o and (best_o['file'],round(best_o['dist'],1)))
    out[day]=res
json.dump(out,open(W+'pick.json','w'),indent=1,default=float)
