import os
"""Fuse BLT side-camera frames into textured vine-wall faces (one per alley side)."""
import json,glob,numpy as np,cv2,sys
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
from pts import frame_points,qmat,Rbc,tbc,D,cam
from scipy import ndimage
Krgb=np.array(cam['K_rgb_scaled']).reshape(3,3)
metas={int(f[-9:-5]):json.load(open(f)) for f in sorted(glob.glob(D+'meta/*.json'))}
P=np.array([metas[i]['pose_map']['position'][:2] for i in range(len(metas))])
r1=P[5:95]; r2=P[115:205]
a=np.polyfit(np.r_[r1[:,1],r2[:,1]],np.r_[r1[:,0],r2[:,0]],1)
U=np.array([a[0],1.0]); U/=np.linalg.norm(U); N=np.array([U[1],-U[0]])
SIDES={'A':dict(frames=range(5,93),near='min'),'B':dict(frames=range(114,206),near='max')}
GZ=(0.15,1.55); GEO=0.02; TEX=0.0025
out={}
for name,cfg in SIDES.items():
    pts=[];fr=[]
    for i in cfg['frames']:
        pw,col,m=frame_points(i)
        n=pw[:,:2]@N; s=pw[:,:2]@U; z=pw[:,2]
        wall=np.median(n)
        k=(np.abs(n-wall)<0.45)&(z>GZ[0])&(z<GZ[1])
        pts.append(np.c_[s[k],n[k],z[k]])
    pts=np.vstack(pts)
    s0=np.floor(pts[:,0].min()/1)*1; s1=np.ceil(pts[:,0].max())
    ns=int((s1-s0)/GEO); nz=int((GZ[1]-GZ[0])/GEO)
    si=((pts[:,0]-s0)/GEO).astype(int); zi=((pts[:,2]-GZ[0])/GEO).astype(int)
    idx=zi*ns+si
    order=np.argsort(idx); idx_s=idx[order]; nv=pts[order,1]
    uniq,start,cnt=np.unique(idx_s,return_index=True,return_counts=True)
    q=20 if cfg['near']=='min' else 80
    g=np.full(ns*nz,np.nan); c=np.zeros(ns*nz)
    for u_,st,ct in zip(uniq,start,cnt):
        g[u_]=np.percentile(nv[st:st+ct],q); c[u_]=ct
    g=g.reshape(nz,ns); c=c.reshape(nz,ns)
    meas=c>=2
    # fill small holes (<=4 cells) for geometry, keep mask of measured
    filled=g.copy(); bad=~meas
    di,(ii,jj)=ndimage.distance_transform_edt(bad,return_indices=True)
    filled=g[ii,jj]; shown=di<=4
    med=np.nanmedian(g); filled=np.clip(filled,med-0.22,med+0.22)
    filled=ndimage.median_filter(filled,7); filled=ndimage.gaussian_filter(filled,4.0); filled=med+(filled-med)*0.6
    out[name]=dict(s0=s0,ns=ns,nz=nz,n=filled,shown=shown,meas=meas,frames=list(cfg['frames']))
    print(name,'s',s0,s1,'grid',ns,nz,'measured %.2f shown %.2f'%(meas.mean(),shown.mean()),'face n median %.2f'%np.nanmedian(g))
np.savez_compressed(os.environ.get('BLT_WORK','/tmp/blt_work/')+'geo.npz',U=U,N=N,**{f'{k}_{kk}':v for k,d in out.items() for kk,v in d.items() if kk!='frames'})
# texture
for name,d in out.items():
    tw=int(d['ns']*GEO/TEX); th=int(d['nz']*GEO/TEX)
    ss=d['s0']+(np.arange(tw)+0.5)*TEX; zz=GZ[0]+(np.arange(th)+0.5)*TEX
    S,Z=np.meshgrid(ss,zz)
    nn=cv2.resize(d['n'].astype(np.float32),(tw,th),interpolation=cv2.INTER_LINEAR)
    sh=cv2.resize(d['shown'].astype(np.uint8),(tw,th),interpolation=cv2.INTER_NEAREST)>0
    X=np.stack([S*U[0]+nn*N[0],S*U[1]+nn*N[1],Z],-1)
    best=np.full((th,tw),np.inf); tex=np.zeros((th,tw,3),np.uint8); src=np.full((th,tw),-1,np.int16); see=np.zeros((th,tw),bool)
    for i in d['frames']:
        m=metas[i]; p=m['pose_map']; Rwb=qmat(p['orientation_xyzw']); twb=np.array(p['position'])
        sc=np.array(p['position'][:2])@U
        cols=np.where(np.abs(ss-sc)<1.2)[0]
        if not len(cols): continue
        c0,c1=cols[0],cols[-1]+1
        Xw=X[:,c0:c1].reshape(-1,3)
        pb=(Xw-twb)@Rwb   # world->base
        pc=(pb-tbc)@Rbc   # base->cam
        zc=pc[:,2]; ok=zc>0.1
        u=Krgb[0,0]*pc[:,0]/zc+Krgb[0,2]; v=Krgb[1,1]*pc[:,1]/zc+Krgb[1,2]
        ok&=(u>=0)&(u<1279)&(v>=0)&(v<719)
        score=np.abs(u-Krgb[0,2])/640+np.abs(v-Krgb[1,2])/720*0.3
        dimg=cv2.imread(D+f'depth/{i:04d}.png',-1).astype(np.float32)/1000
        dz=cv2.remap(dimg,(u/4).reshape(th,-1).astype(np.float32),(v/4).reshape(th,-1).astype(np.float32),cv2.INTER_NEAREST).ravel()
        thru=(dz<=0)|(dz>zc+0.35)
        score=score+thru*1.0
        score[~ok]=np.inf
        score=score.reshape(th,c1-c0); thru=thru.reshape(th,c1-c0)
        img=cv2.imread(D+f'rgb/{i:04d}.jpg')
        samp=cv2.remap(img,u.reshape(th,-1).astype(np.float32),v.reshape(th,-1).astype(np.float32),cv2.INTER_LINEAR)
        b=best[:,c0:c1]; upd=score<b
        b[upd]=score[upd]; tex[:,c0:c1][upd]=samp[upd]; src[:,c0:c1][upd]=i; see[:,c0:c1][upd]=thru[upd]
    hsv=cv2.cvtColor(tex,cv2.COLOR_BGR2HSV).astype(int); B,G,R=[tex[...,k].astype(int) for k in range(3)]
    sky=((hsv[...,2]>165)&(hsv[...,1]<70))|((B>G+8)&(B>R+15)&(hsv[...,2]>140))
    solid=sh&np.isfinite(best)&~see&~sky
    solid=ndimage.binary_opening(solid,iterations=1)
    lab,nl=ndimage.label(solid); sz=ndimage.sum(solid,lab,range(1,nl+1)); solid=np.isin(lab,1+np.where(sz>=1600)[0])
    solid=ndimage.binary_fill_holes(solid)&solid|ndimage.binary_closing(solid,iterations=2)&solid
    solid=ndimage.binary_erosion(solid,iterations=1)
    alpha=cv2.GaussianBlur(solid.astype(np.float32),(3,3),0)
    alpha=(alpha*255).astype(np.uint8)
    tex=tex[::-1]; alpha=alpha[::-1]  # top row = high z
    cv2.imwrite(os.environ.get('BLT_WORK','/tmp/blt_work/')+f'tex_{name}.jpg',tex,[cv2.IMWRITE_JPEG_QUALITY,88])
    cv2.imwrite(os.environ.get('BLT_WORK','/tmp/blt_work/')+f'alpha_{name}.png',alpha)
    np.save(os.environ.get('BLT_WORK','/tmp/blt_work/')+f'src_{name}.npy',src[::-1])
    seen=sh&np.isfinite(best)
    np.save(os.environ.get('BLT_WORK','/tmp/blt_work/')+f'seen_{name}.npy',seen[::-1])  # spots a photo covered (canopy or gap), for flags.py
    print(name,'texture',tw,th,'coverage %.2f'%(alpha>0).mean())
