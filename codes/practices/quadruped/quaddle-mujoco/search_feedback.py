"""Evaluate heading correction through left/right stride amplitude only."""
from concurrent.futures import ProcessPoolExecutor
import json, math
import numpy as np
import mujoco
from search_gait import ROOT, SIGNS


def run(args):
    p,kp,kd,kx=args
    m=mujoco.MjModel.from_xml_path(str(ROOT/'models/scene.xml'));d=mujoco.MjData(m)
    af,ab,bf,bb,hz,rf,rb,lb,h=p
    amps=np.array([af,af,ab,ab]);bias=np.array([bf,bf,bb,bb]);phases=np.array([0,rf,rb,lb])
    start=None;side=0.;yawmax=0.;up=1.;hits=0
    for k in range(3200):
        if k==200:start=d.qpos[:3].copy()
        t=max(0,k/100-2);ramp=min(1,t)
        rot=d.body('body').xmat.reshape(3,3)
        yaw=math.atan2(rot[1,0],rot[0,0])
        steer=np.clip(kp*(yaw+kx*(d.qpos[0]-(start[0] if start is not None else 0)))+kd*d.qvel[5],-.5,.5)
        phase=2*np.pi*hz*t+phases
        wave=(np.sin(phase)+h*np.sin(2*phase))/(1+abs(h))
        d.ctrl[:]=SIGNS*ramp*(bias+amps*(1+steer*SIGNS)*wave)
        mujoco.mj_step(m,d,nstep=10)
        if k>200:
            side=max(side,abs(d.qpos[0]-start[0]));yawmax=max(yawmax,abs(yaw));up=min(up,rot[2,2])
            hits+=int(any(m.geom('body_contact').id in (c.geom1,c.geom2) for c in d.contact))
        if d.warning.number.sum() or up<.6:break
    return dict(params=p,kp=kp,kd=kd,kx=kx,forward=float(start[1]-d.qpos[1]),side=side,yaw=yawmax,up=up,hits=hits,time=d.time)


if __name__=='__main__':
    (ROOT/'outputs').mkdir(exist_ok=True)
    best_file = ROOT/'outputs/gait_search_best.json'
    if not best_file.exists():
        best_file = ROOT/'reference/previous-search-best.json'
    best=json.loads(best_file.read_text())['params']
    bound=[.3,.3,-.25,-.25,3,0,np.pi,np.pi,0]
    samples=[(p,kp,.03,2.) for p in [best,bound] for kp in [-2.,-1.,-.5,.2,.5,1.,2.]]
    with ProcessPoolExecutor(4) as pool:
        results=list(pool.map(run,samples))
    results.sort(key=lambda r:r['forward']-3*r['side']-.2*r['yaw']-.05*r['hits'],reverse=True)
    (ROOT/'outputs/gait_feedback_search.json').write_text(json.dumps(results,indent=2)+'\n')
    print(json.dumps(results,indent=2),flush=True)
