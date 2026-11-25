"""Frozen overlapping slot trackers: native target checks, modal spectra and integration audit."""
import argparse
import csv
from dataclasses import replace
from fractions import Fraction
import gzip
from itertools import combinations
import json
import os
from pathlib import Path
import sys

# Only dense small eigenproblems are evaluated here.
os.environ["OPENBLAS_NUM_THREADS"]="1"
os.environ["MKL_NUM_THREADS"]="1"
import numpy as np
from scipy.linalg import eigvals

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
DEFAULT_SOURCE=HERE/"nearest_segment_base.zip"
N_VALUES=(6,7,8,9,11,12,13,16,20,23,24,25,32,36,48,64,72,96,144)


def shapes(k,n):
    layers,r=divmod(n,k)
    if k==2:
        for first in (0,1):
            yield f"phase{first}",[(first^(j%2),j/2) for j in range(n)]
        return
    tails=list(combinations(range(k),r))
    if k==3:
        tails=[s for s in tails if 1 not in s]
    for tail in tails:
        slots=[(lane,i+(lane%2)/2) for i in range(layers) for lane in range(k)]
        slots.extend((lane,layers+(lane%2)/2) for lane in tail)
        yield "tail"+("".join(map(str,tail)) or "-"),slots


def native_step(cars,k):
    """Run the native target and the native longitudinal speed law before overrides."""
    from noa import native_rules as r,staggered
    n=len(cars);P=np.zeros((n,n));target=np.empty(n);speeds=np.empty(n)
    for i,c in enumerate(cars):
        rows=[v for v in cars if v is not c and -r.REAR_VIEW<=v.x-c.x<=r.FRONT_VIEW]
        group=list(reversed(r._local_group(c,rows)))
        cols=[v.track for v in group];P[i,cols]=1/len(cols)
        spacing=r.desired_spacing(sum(v.speed for v in group)/len(group))
        matched=staggered.choose_target(group.index(c),group,k,spacing,
                      head_clipped=group[0].x-c.x>r.FRONT_VIEW-r.GROUP_GAP,
                      tail_clipped=c.x-group[-1].x>r.REAR_VIEW-r.GROUP_GAP,
                      sensor_bounds=(c.x-r.REAR_VIEW,c.x+r.FRONT_VIEW))
        if matched.lane!=c.lane:
            raise ValueError("This physical arrangement induces a lateral reassignment")
        target[i]=matched.x
        speeds[i]=r._shape_speed(c,matched.x)
    positions=np.array([c.x for c in cars])+r.CONTROL_STEP*speeds
    return P,target,np.r_[positions,speeds]


def native_direction(cars,k,direction,eps=1e-4):
    n=len(cars);values=[]
    for sign in (-1,1):
        sample=[replace(c,x=c.x+sign*eps*direction[i],speed=c.speed+sign*eps*direction[n+i])
                for i,c in enumerate(cars)]
        values.append(native_step(sample,k)[2])
    return (values[1]-values[0])/(2*eps)


def dynamics(P,levels,omega,H,h):
    n=len(P);I=np.eye(n);beta=P@levels-levels
    K=omega**2*(P-I)
    B=-2*omega*I+omega**2*H*beta[:,None]*P
    # q_i-q_last for i<n-1; keep all absolute speed errors.
    diff=np.column_stack((np.eye(n-1),-np.ones(n-1)))
    Kr=K[:,:-1]
    A=np.block([[np.zeros((n-1,n-1)),diff],[Kr,B]])
    U=I+h*B
    step=np.block([[np.eye(n-1)+h*h*diff@Kr,h*diff@U],[h*Kr,U]])
    full=np.block([[I+h*h*K,h*U],[h*K,U]])
    return beta,A,step,full


def constant_roots(P,omega,h):
    eigP=eigvals(P);a=h*omega
    roots=np.concatenate([np.roots((1.,-(2-2*a-a*a+a*a*z),1-2*a)) for z in eigP])
    neutral=np.argmin(abs(roots-1))
    assert abs(roots[neutral]-1)<1e-9
    return np.delete(roots,neutral)


def exact_contraction(P,levels,omega,H,h,float_step,*,updated_velocity):
    """Certify a matrix power contracts using fixed-point products and integer error bounds."""
    # Each exact coefficient is a rational from an integer occupancy, a half-row,
    # and the nominal decimal controller constants. No floating eigensolver is used.
    w,T,dt=(Fraction(str(v)) for v in (omega,H,h))
    n=len(P);d=2*n-1
    B=2**24;S=B**2
    twice=np.rint(2*levels).astype(int).tolist()
    rows=[]
    for i,p in enumerate(P):
        cols=np.flatnonzero(p).tolist()
        count=len(cols)
        beta=Fraction(sum(twice[j] for j in cols)-count*twice[i],2*count)
        row={n-1+i:1-2*dt*w}
        if i<n-1:row[i]=-dt*w*w
        for j in cols:
            if j<n-1:row[j]=row.get(j,0)+dt*w*w/count
            col=n-1+j
            row[col]=row.get(col,0)+dt*w*w*T*beta/count
        rows.append(row)
    quant=np.zeros((d,d),dtype=np.int64)
    for i,row in enumerate(rows):
        for j,v in row.items():quant[n-1+i,j]=round(v*S)
        if i<n-1 and updated_velocity:
            for j in (row.keys() | rows[-1].keys() | {i}):
                value=int(j==i)+dt*(row.get(j,0)-rows[-1].get(j,0))
                quant[i,j]=round(value*S)
        elif i<n-1:
            # A certificate for I+hA places all continuous poles in Re(s)<0.
            quant[i,i]=S
            quant[i,n-1+i]=round(dt*S)
            quant[i,d-1]=-round(dt*S)
    assert np.max(abs(quant.astype(float)/S-float_step))<3e-14
    error=(d+1)//2   # infinity-norm error in units of 1/S
    for exponent in range(15):
        assert d*max(abs(int(quant.min())),abs(int(quant.max())))<2**63
        norm=int(np.max(np.sum(abs(quant),axis=1)))
        if norm+error<S:
            return 2**exponent,(norm+error)/S
        high,low=np.divmod(quant,B)
        max_digit=max(B,int(abs(high).max()))
        # Every scalar dot-product partial sum and subsequent combination fits int64.
        assert 5*d*max_digit**2+4*S<2**63
        cross=high@low+low@high
        quotient,remainder=np.divmod(cross,B)
        quant=high@high+quotient+(remainder*B+low@low+S//2)//S
        # For A exact, Q approximate: ||A²-Q²|| <= 2||Q||e+e².
        error=(2*norm*error+error*error+S-1)//S+(d+1)//2
    raise ArithmeticError("Could not certify contraction for this finite template")


def check_shape(k,n,shape,slots,rng):
    from noa import native_rules as r
    w,h,H=r.SHAPE_FREQUENCY,r.CONTROL_STEP,r.HEADWAY
    D=r.desired_spacing(r.CRUISE)
    # Even the longest (144-car two-lane) shape fits inside the unpreviewed
    # part of a 2800 m approach; translation leaves the mathematical graph unchanged.
    levels=np.array([u for _,u in slots]);x=2500.-D*levels
    cars=[r.Vehicle(i,x[i],(lane+.5)*r.LANE_WIDTH,r.CRUISE,lane) for i,(lane,_) in enumerate(slots)]
    P,target,_=native_step(cars,k)
    eqerr=max(abs(target-x))
    if eqerr>1e-8:raise ValueError(f"Not an equilibrium: {k},{n},{shape},{eqerr}")
    # Independently reconstruct the sensor incidence using only physical x.
    offsets=x[None,:]-x[:,None]
    visible=(offsets>=-r.REAR_VIEW)&(offsets<=r.FRONT_VIEW)
    assert np.max(abs(P-visible/visible.sum(axis=1)[:,None]))<1e-12
    beta,A,M,full=dynamics(P,levels,w,H,h)
    _,_,M0,_=dynamics(P,levels,w,0.,h)
    roots=eigvals(M);continuous=eigvals(A)
    r0=max(abs(constant_roots(P,w,h)))
    assert abs(r0-max(abs(eigvals(M0))))<1e-7
    direction=rng.uniform(-1,1,2*n)
    observed=native_direction(cars,k,direction)
    derivative_error=max(abs(observed-full@direction))
    assert derivative_error<2e-7,(k,n,shape,derivative_error)
    power,upper=exact_contraction(P,levels,w,H,h,M,updated_velocity=True)
    cont_power,cont_upper=exact_contraction(P,levels,w,H,h,np.eye(len(A))+h*A,
                                           updated_velocity=False)
    return dict(lanes=k,n=n,shape=shape,front_view_m=r.FRONT_VIEW,rear_view_m=r.REAR_VIEW,
                neighborhood_min=int(visible.sum(axis=1).min()),neighborhood_max=int(visible.sum(axis=1).max()),
                min_beta=round(min(beta),8),max_beta=round(max(beta),8),
                constant_rho=r0,dynamic_continuous_abscissa=max(continuous.real),
                dynamic_rho=max(abs(roots)),certified_power=power,power_norm_upper=upper,
                continuous_test_power=cont_power,continuous_test_norm_upper=cont_upper,
                target_error_m=eqerr,native_derivative_error=derivative_error)


def trace_update(path):
    from noa import native_rules as r
    h=r.CONTROL_STEP;prev={};n=0;ss=np.zeros(3);worst=np.zeros(3)
    with gzip.open(path,"rt") as f:
        for line in f:
            fr=json.loads(line);states=fr["states"]
            for name,v in states.items():
                old=prev.get(name)
                if old is None or not 20<old[0]<v[0]<780 or abs(old[1]-v[1])>1e-8:continue
                if abs(v[1]/3.3-.5-round(v[1]/3.3-.5))>1e-8 or abs(v[2]-old[2])<.02:continue
                velocities=np.array((v[2],(v[2]+old[2])/2,old[2]))
                e=v[0]-old[0]-h*velocities
                ss+=e*e;worst=np.maximum(worst,abs(e));n+=1
            prev=states
    assert n and worst[0]<1e-9
    return n,worst,np.sqrt(ss/n)


def independent_branch_check():
    from noa import native_rules as r
    slots=next(shapes(3,12))[1];D=r.desired_spacing(r.CRUISE)
    cars=[r.Vehicle(i,600.-D*u,(lane+.5)*3.3,r.CRUISE,lane) for i,(lane,u) in enumerate(slots)]
    perturbed=[replace(c,x=c.x-.001) if i==0 else c for i,c in enumerate(cars)]
    ego=perturbed[3]
    rows=[v for v in perturbed if v is not ego and -100<=v.x-ego.x<=200]
    _,_,state=native_step(perturbed,3)
    command,_=r._transport(ego,rows,r.Memory(),3,3,False)
    cap=r.safe_speed(ego,rows)
    assert cap>state[15]>command.speed and abs(command.speed-28.79994)<1e-11
    # Independent finite-difference Jacobian on all (q,u) coordinate axes.
    P,_,_=native_step(cars,3)
    full=dynamics(P,np.array([v for _,v in slots]),r.SHAPE_FREQUENCY,r.HEADWAY,r.CONTROL_STEP)[3]
    actual=np.column_stack([native_direction(cars,3,col) for col in np.eye(24)])
    error=np.max(abs(actual-full))
    assert error<2e-7
    return state[15],command.speed,cap,error


def main(source,csv_path,trace):
    sys.path.insert(0,str(source.resolve()))
    from noa import native_rules as r
    rng=np.random.default_rng(112552);rows=[]
    for k in (2,3,4):
        for n in N_VALUES:
            for code,rowspec in shapes(k,n):
                rows.append(check_shape(k,n,code,rowspec,rng))
    if csv_path:
        with csv_path.open("x",newline="",encoding="utf8") as f:
            writer=csv.DictWriter(f,rows[0]);writer.writeheader();writer.writerows(rows)
    for k in (2,3,4):
        block=[a for a in rows if a["lanes"]==k]
        worst=max(block,key=lambda t:t["dynamic_rho"])
        print(k,len(block),"max nontranslation radius",worst["n"],worst["shape"],worst["dynamic_rho"])
    print("equilibrium and finite-difference worst",max(a["target_error_m"] for a in rows),
          max(a["native_derivative_error"] for a in rows))
    # Two internally consistent platoons. The genuine local-group cutoff keeps
    # the relative position of the disconnected platoons neutral.
    slots=next(shapes(3,12))[1];D=r.desired_spacing(r.CRUISE)
    raw=[(j,300.-D*u) for j,u in slots];tail=min(x for _,x in raw)
    raw.extend([(lane,tail-70.-D*u) for lane,u in slots])
    cs=[r.Vehicle(i,x,(l+.5)*3.3,r.CRUISE,l) for i,(l,x) in enumerate(raw)]
    P,_,_=native_step(cs,3);levels=np.array([(300.-v.x)/D for v in cs])
    _,A,M,_=dynamics(P,levels,r.SHAPE_FREQUENCY,r.HEADWAY,r.CONTROL_STEP)
    remaining=sum(abs(eigvals(M)-1)<1e-8)
    assert remaining==1 and sum(abs(eigvals(A))<1e-8)==1
    print("two groups 70 m apart: additional neutral shape modes",remaining)
    print("before/after real-front override, safety cap, 12-car Jacobian error:",independent_branch_check())
    if trace:print("new, midpoint, old-speed physical update errors:",trace_update(trace))


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--source",type=Path,default=DEFAULT_SOURCE)
    p.add_argument("--csv",type=Path);p.add_argument("--trace",type=Path)
    args=p.parse_args();main(args.source,args.csv,args.trace)
