import os
import json,glob,numpy as np,cv2,math,sys
D=os.path.join(os.path.dirname(os.path.abspath(__file__)),'../../viewer/demo-data/blt_sample/')
cam=json.load(open(D+'camera.json'))
Kd=np.array(cam['K_depth_scaled']).reshape(3,3)
mc=cam['camera_to_base']['urdf_candidate']
def qmat(q):
    x,y,z,w=q
    return np.array([[1-2*(y*y+z*z),2*(x*y-z*w),2*(x*z+y*w)],[2*(x*y+z*w),1-2*(x*x+z*z),2*(y*z-x*w)],[2*(x*z-y*w),2*(y*z+x*w),1-2*(x*x+y*y)]])
Rbc=qmat(mc['rotation_xyzw']); tbc=np.array(mc['translation'])
H,W=180,320
u,v=np.meshgrid(np.arange(W),np.arange(H))
rays=np.stack([(u-Kd[0,2])/Kd[0,0],(v-Kd[1,2])/Kd[1,1],np.ones_like(u,float)],-1)
def frame_points(i,maxd=3.0):
    m=json.load(open(D+f'meta/{i:04d}.json'))
    d=cv2.imread(D+f'depth/{i:04d}.png',-1).astype(float)/1000
    rgb=cv2.imread(D+f'rgb/{i:04d}.jpg')[:,:,::-1]
    ok=(d>0.2)&(d<maxd)
    pc=rays[ok]*d[ok][:,None]
    col=cv2.resize(rgb,(W,H),interpolation=cv2.INTER_AREA)[ok]
    pb=pc@Rbc.T+tbc
    p=m['pose_map']; Rwb=qmat(p['orientation_xyzw']); twb=np.array(p['position'])
    pw=pb@Rwb.T+twb
    return pw,col,m
if __name__=='__main__':
    P=np.array([json.load(open(f))['pose_map']['position'][:2] for f in sorted(glob.glob(D+'meta/*.json'))])
    r1=P[5:95]; r2=P[115:205]
    a=np.polyfit(np.r_[r1[:,1],r2[:,1]],np.r_[r1[:,0],r2[:,0]],1)  # placeholder
    dirv=np.array([a[0],1.0]); dirv/=np.linalg.norm(dirv); n=np.array([dirv[1],-dirv[0]])
    print('dir',dirv,'normal',n)
    for i in list(range(5,95,10))+list(range(115,205,10)):
        pw,col,m=frame_points(i)
        rob=np.array(m['pose_map']['position'][:2])
        print(i, 'robot n=%.2f'%(rob@n), 'wall n med=%.2f'%np.median(pw[:,:2]@n), 'z 5/95=%.2f %.2f'%tuple(np.percentile(pw[:,2],[5,95])), len(pw))
