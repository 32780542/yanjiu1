"""Longitudinal reachability for an assigned moving template and mean-origin PD.

Set rho_i=x_i+d_i. A slot at time T is a-d_i+vc*T. In the vc frame each
car must cover a-rho_i and finish at zero relative speed. Upper/lower
displacement extrema integrate the accelerating/decelerating velocity
envelopes. Convex combinations of those two controls attain every point in
the interval. Cars are independent and positions are otherwise unrestricted.
The computation models symmetric acceleration limits; the simulation has
additional car-following, lane-change, speed and safety constraints.

For equal initial and final speed vc and A>0, the relative reach in direction
u is AT²/4 up to T=2u/A and uT-u²/A afterwards. The feasible origin interval
is [max(rho)-reach_down, min(rho)+reach_up]. At the earliest positive T the
ends coincide. Inverting the sum of the two reaches gives common_speed().
The least-squares origin mean(rho) equals this minimax origin only when the
two directional extremal trip times balance. With both caps inactive,
T_mean/T_opt = sqrt(1+2*abs(mean-midrange)/span), for span>0.

For fixed relative slot ranks c, common speed vbar, unsaturated PD and mean
translation, define eta=rho-mean(rho), D=D0+H*vbar. The common speed error
satisfies m'=-2*omega*m. With z=x-xbar+(c-cbar)*D(vc), the z forcing is
-omega²*(c-cbar)*H*m. Adding H*(c-cbar)*m gives exactly homogeneous
eta''+2*omega*eta'+omega²*eta=0. If
  span(eta0)+span(eta_dot0)/(e*omega) < switch_span,
then the continuous mean-origin branch stays inside that switching interval,
conditional on fixed slots/members and all other clamps remaining inactive.
The code checks the corresponding two-pole discrete bound. For a receding
common origin shifted by b=a-mean(rho), m' instead gains omega²*b, and the
smooth-branch eta equation gains omega²*H*(c-cbar)*b'.
"""
import json
from math import inf, isclose, sqrt

import numpy as np
from scipy.integrate import solve_ivp
from scipy.optimize import linprog


def distance(t, initial, cap, accel):
    """Max signed displacement from relative speed initial to zero."""
    if t < abs(initial)/accel-1e-10:
        raise ValueError("insufficient time to reach terminal speed")
    peak = (initial+accel*t)/2
    area = peak**2 if peak <= cap else 2*cap*peak-cap**2
    return (area-initial**2/2)/accel


def interval(t,rho,initial,up,down,accel):
    return (max(r-distance(t,-v,down,accel) for r,v in zip(rho,initial)),
            min(r+distance(t,v,up,accel) for r,v in zip(rho,initial)))


def common_speed(rho,up,down,accel):
    span = max(rho)-min(rho)
    if span == 0:
        return 0.,min(rho)
    if up+down == 0:
        return inf,None
    m,M = sorted((up,down))
    if span <= 2*m*m/accel:
        t = sqrt(2*span/accel)
    elif span <= (M*M+2*m*M-m*m)/accel:
        t = 2*(sqrt(2*m*m+accel*span)-m)/accel
    else:
        t = (span+(m*m+M*M)/accel)/(m+M)
    return t,min(rho)+distance(t,0,up,accel)


def travel_time(dx,cap,accel):
    if dx == 0:
        return 0.
    if cap == 0:
        return inf
    return 2*sqrt(dx/accel) if dx<=cap*cap/accel else dx/cap+cap/accel


def unequal_speed(rho,initial,up,down,accel):
    if not all(-down<=v<=up for v in initial):
        raise ValueError("initial vehicle speed outside its physical bounds")
    if up+down==0:
        return (0.,(min(rho),max(rho))) if min(rho)==max(rho) else (inf,None)
    lo = max(abs(v) for v in initial)/accel
    def feasible(t):
        a,b = interval(t,rho,initial,up,down,accel)
        return a<=b
    if feasible(lo):
        return lo,interval(lo,rho,initial,up,down,accel)
    hi = max(1.,2*lo)
    while not feasible(hi):
        hi *= 2
    for _ in range(64):
        middle = (lo+hi)/2
        if feasible(middle):
            hi = middle
        else:
            lo = middle
    return hi,interval(hi,rho,initial,up,down,accel)


def grid_feasible(t,rho,initial,up,down,accel,steps=40):
    """Independent LP: piecewise-linear velocities, exact trapezoid positions."""
    n = len(rho)
    dt = t/steps
    vars_n = n*(steps+1)+1
    eq = np.zeros((n,vars_n))
    ine = np.zeros((2*n*steps,vars_n))
    bounds = []
    for i,v in enumerate(initial):
        off = i*(steps+1)
        bounds.extend([(v,v)]+[(-down,up)]*(steps-1)+[(0,0)])
        eq[i,off:off+steps+1] = dt
        eq[i,off] = eq[i,off+steps] = dt/2
        eq[i,-1] = -1
        for k in range(steps):
            r = 2*(i*steps+k)
            ine[r,off+k:off+k+2] = [-1,1]
            ine[r+1] = -ine[r]
    return linprog(np.zeros(vars_n),A_ub=ine,b_ub=np.full(2*n*steps,accel*dt),
                   A_eq=eq,b_eq=-np.array(rho),bounds=bounds+[(None,None)],method="highs").success


def check_motion():
    a = 5.
    common = heterogeneous = 0
    for up,down in ((4.5,28.8),(28.8,4.5),(6.,6.),(0.,12.),(12.,0.)):
        m,M = sorted((up,down))
        cuts = (2*m*m/a,(M*M+2*m*M-m*m)/a)
        for s in sorted({.1,3.,35.,250.,500.,*cuts}):
            if s == 0:
                continue
            rho = (0.,s*.35,s)
            t,origin = common_speed(rho,up,down,a)
            lo,hi = interval(t,rho,[0]*3,up,down,a)
            assert isclose(lo,origin,abs_tol=1e-9) and isclose(hi,origin,abs_tol=1e-9)
            assert not grid_feasible(t*.995,rho,[0]*3,up,down,a)
            assert grid_feasible(t*1.005,rho,[0]*3,up,down,a)
            common += 1
    rng = np.random.default_rng(1125)
    for _ in range(20):
        rho = rng.uniform(-25,25,4)
        initial = rng.uniform(-6,4,4)
        t,(lo,hi) = unequal_speed(rho,initial,4.5,28.8,a)
        assert lo<=hi and not grid_feasible(t*.995,rho,initial,4.5,28.8,a)
        assert grid_feasible(t*1.005,rho,initial,4.5,28.8,a)
        heterogeneous += 1
    # Compare the continuous envelopes with numerical time integration.
    for w in (-8.,-2.,0.,3.):
        for t in (2.,8.,15.):
            ts = np.linspace(0,t,20001)
            upper = np.minimum(np.minimum(4.5,w+a*ts),a*(t-ts))
            lower = np.maximum(np.maximum(-28.8,w-a*ts),-a*(t-ts))
            assert abs(np.trapezoid(upper,ts)-distance(t,w,4.5,a))<1e-6
            assert abs(np.trapezoid(lower,ts)+distance(t,-w,28.8,a))<1e-6
    examples = []
    for rho in ((0.,4.,4.),(0.,60.,60.)):
        t,origin = common_speed(rho,4.5,28.8,a)
        mean = sum(rho)/len(rho)
        tmean = max(travel_time(mean-min(rho),4.5,a),travel_time(max(rho)-mean,28.8,a))
        examples.append(dict(rho=rho,optimal_time_s=round(t,5),optimal_origin_m=round(origin,5),
                             mean_origin_m=round(mean,5),mean_time_s=round(tmean,5)))
    return dict(common_speed_lp_brackets=common,unequal_speed_lp_brackets=heterogeneous,
                envelope_integrals=24,examples=examples)


def check_pd():
    w,h,vc,H = 2.,.1,28.8,.85
    s = w*h
    trace,det = 2-2*s-s*s,1-2*s
    roots = np.roots((1.,-trace,det))
    c = np.array((0.,.5,1.,1.5,2.,2.5))
    centered = c-c.mean()
    x = 100-c*(5.5+H*vc)+np.array((.12,-.1,.04,.08,-.13,.02))
    v = vc+np.array((.23,.17,-.05,.07,.17,-.08))
    # Continuous reference obtained by integrating the physical vehicle ODEs.
    def derivatives(t,state):
        pos,vel = np.split(state,2)
        offsets = c*(5.5+H*vel.mean())
        return np.r_[vel,w*w*((pos+offsets).mean()-offsets-pos)+2*w*(vc-vel)]
    times = np.linspace(0,5,51)
    ref = solve_ivp(derivatives,(0.,5.),np.r_[x,v],t_eval=times,rtol=1e-12,atol=1e-12)
    pos,vel = np.split(ref.y,2)
    rho = pos+c[:,None]*(5.5+H*vel.mean(axis=0))
    eta0 = rho[:,0]-rho[:,0].mean()
    rate0 = v-v.mean()-2*w*centered*H*(v.mean()-vc)
    direct = (eta0[:,None]*(1+w*times)+rate0[:,None]*times)*np.exp(-w*times)
    max_ode_error = np.max(abs(direct-(rho-rho.mean(axis=0))))
    assert max_ode_error<1e-8
    residuals = []
    max_a = max_recurrence = 0.
    for _ in range(102):
        spacing = 5.5+H*v.mean()
        rho = x+c*spacing
        eta = rho-rho.mean()
        residuals.append(eta)
        acc = w*w*(rho.mean()-c*spacing-x)+2*w*(vc-v)
        # Direct z-equation, with the live average speed in the forcing.
        z = x-x.mean()+centered*(5.5+H*vc)
        rhs = -2*w*(v-v.mean())-w*w*z-w*w*centered*H*(v.mean()-vc)
        assert np.allclose(acc-acc.mean(),rhs,atol=1e-12)
        assert isclose(acc.mean(),2*w*(vc-v.mean()),abs_tol=1e-12)
        max_a = max(max_a,abs(acc).max())
        v = v+h*acc
        x = x+h*v
    for a,b,curr in zip(residuals,residuals[1:],residuals[2:]):
        max_recurrence = max(max_recurrence,max(abs(curr-trace*b+det*a)))
    assert max_recurrence<1e-11 and max_a<5.
    # For positive roots both <=1, the sum of coefficient ranges bounds
    # the residual span for all k, providing a discrete mean-branch certificate.
    big,small = sorted(roots,reverse=True)
    coef1 = (residuals[1]-small*residuals[0])/(big-small)
    coef2 = residuals[0]-coef1
    bound = np.ptp(coef1)+np.ptp(coef2)
    spans = [np.ptp(r) for r in residuals]
    assert max(spans)<=bound+1e-12
    return dict(mean_speed_pole=det,shape_poles=list(np.round(roots,8)),
                continuous_ode_error_m=max_ode_error,
                maximum_recurrence_error_m=float(max_recurrence),acceleration_max_mps2=float(max_a),
                verified_steps=100,initial_span_m=spans[0],max_span_m=max(spans),
                conservative_all_time_span_bound_m=bound,span_at_10s_m=spans[100])


if __name__=="__main__":
    print(json.dumps(dict(reachability=check_motion(),mean_origin_pd=check_pd()),indent=2))
