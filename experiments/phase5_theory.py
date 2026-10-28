"""Replayable fixed-reference longitudinal calculation; standard library only.

This is an offline analysis, never a source of controller actions or references.
Run with python -I -B -S experiments/phase5_theory.py --run.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def continuous_characteristic(kp, kv, k0, tau, weight=1., control_dt=0.):
    """Descending coefficients of the continuously updated feedback proxy.

At h>0 retain NOA's -k0*h*a/2 term. This proxy is not the actual ZOH map.
"""
    return [tau, 1.+k0*control_dt/2, k0+weight*kv, weight*kp]


def zoh_matrix(kp, kv, k0, tau, weight=1., control_dt=.1):
    """Exact held-command map of x=(e,w,a), including NOA midpoint term."""
    h = control_dt
    one_minus_q = -math.expm1(-h/tau)
    q = 1.-one_minus_q
    displacement_a = tau*h-tau*tau*one_minus_q
    displacement_u = h*h/2-displacement_a
    phi = [[1., h, -displacement_a],
           [0., 1., -tau*one_minus_q], [0., 0., q]]
    gamma = [-displacement_u, -(h-tau*one_minus_q), one_minus_q]
    feedback = [weight*kp, k0+weight*kv, -k0*h/2]
    return [[phi[i][j]+gamma[i]*feedback[j] for j in range(3)] for i in range(3)]


def eigenvalues3(matrix):
    """Real-coefficient cubic roots via its depressed cubic (no NumPy needed)."""
    m = matrix
    trace = sum(m[i][i] for i in range(3))
    second = sum(m[i][i]*m[j][j]-m[i][j]*m[j][i]
                 for i in range(3) for j in range(i+1, 3))
    determinant = (m[0][0]*(m[1][1]*m[2][2]-m[1][2]*m[2][1])
                   -m[0][1]*(m[1][0]*m[2][2]-m[1][2]*m[2][0])
                   +m[0][2]*(m[1][0]*m[2][1]-m[1][1]*m[2][0]))
    a, b, c = -trace, second, -determinant
    p, q = b-a*a/3, 2*a*a*a/27-a*b/3+c
    discriminant = (q/2)**2+(p/3)**3
    if discriminant < 0:
        radius = 2*math.sqrt(-p/3)
        angle = math.acos(max(-1., min(1., -q/(2*math.sqrt(-(p/3)**3)))))
        roots = [complex(radius*math.cos((angle+2*j*math.pi)/3)-a/3)
                 for j in range(3)]
    else:
        def cbrt(value):
            return math.copysign(abs(value)**(1/3), value)
        u, v = cbrt(-q/2+math.sqrt(discriminant)), cbrt(-q/2-math.sqrt(discriminant))
        roots = [complex(u+v-a/3), complex(-(u+v)/2-a/3, math.sqrt(3)*(u-v)/2),
                 complex(-(u+v)/2-a/3, -math.sqrt(3)*(u-v)/2)]
    return sorted(roots, key=lambda z:(z.real, z.imag))


def kinematic_jacobian(model, kp, kv, k0, weight, control_dt, integration_dt,
                       epsilon=1e-3):
    """Central differences of actual KinematicModel.advance at v_ref=v0=5."""
    from models.kinematic import kinematic_state
    from models.vehicle import Actuation
    h, v0 = control_dt, 5.

    def transition(x):
        e, w, acceleration = x
        state = kinematic_state(model.p, x_m=-e, vx_mps=v0-w,
                                a_drive_mps2=acceleration)
        u = weight*kp*e+(k0+weight*kv)*w-k0*h*acceleration/2
        step = model.advance(state, Actuation(u, 0.), h, integration_dt)
        final = step.final
        return [v0*h-final.x_m, v0-final.vx_mps, final.a_drive_mps2]

    columns = []
    for j in range(3):
        plus, minus = [0.]*3, [0.]*3
        plus[j], minus[j] = epsilon, -epsilon
        plus_result, minus_result = transition(plus), transition(minus)
        columns.append([(p-m)/(2*epsilon) for p,m in zip(plus_result,minus_result)])
    return [[columns[j][i] for j in range(3)] for i in range(3)]


def reference_speed_response(omega, kp, kv, k0, tau, weight=1., control_dt=0.):
    """Continuous proxy V_i/V_ref with the shared absolute target held fixed."""
    s = 1j*omega
    coefficients = continuous_characteristic(kp,kv,k0,tau,weight,control_dt)
    denominator = ((coefficients[0]*s+coefficients[1])*s+coefficients[2])*s+coefficients[3]
    return weight*(kp+kv*s)/denominator


def build_report():
    from models.kinematic import KinematicModel
    from research.common import settings
    model = KinematicModel.from_config()
    formation, noa = settings('phase5'), settings('phase4')
    kp, kv = formation['formation_kp_per_s2'], formation['formation_kv_per_s']
    k0, tau = noa['noa_speed_gain_per_s'], model.p['acceleration_lag_s']
    report = {
        'schema':'phase5_fixed_reference_theory_v1',
        'scope':{'claim':'fixed_reference_cruise_branch_only',
                 'fixed_weight':1., 'reference_speed_mps':5.,
                 'requires':['fixed reference and lanes', 'constant desired offset',
                             'cruise branch active', 'no saturation or speed boundary',
                             'jerk clip inactive', 'safety increment accepted',
                             'constant full confidence after fade', 'same-time ideal local observation'],
                 'not_proved':['switching topology', 'global formation convergence',
                               'actual sampled switched string stability', 'high-speed feasibility',
                               'collision freedom outside inherited conditional checks']},
        'parameters':{'kp_per_s2':kp, 'kv_per_s':kv, 'k0_per_s':k0, 'tau_s':tau,
                      'increment_limit_mps2':formation['formation_accel_limit_mps2'],
                      'actuator_jerk_limit_mps3':model.p['actuator_jerk_limit_mps3']},
        'continuous':[], 'sampled':[]}
    for h in (0., .1, .05):
        c = continuous_characteristic(kp,kv,k0,tau,1.,h)
        companion = [[0.,1.,0.], [0.,0.,1.], [-c[3]/c[0],-c[2]/c[0],-c[1]/c[0]]]
        poles = eigenvalues3(companion)
        b, k = 1+k0*h/2, k0+kv
        # |den(jw)|^2-|num(jw)|^2 = w^2*(C0+C2*w^2+tau^2*w^4).
        c0, c2 = k*k-2*b*kp-kv*kv, b*b-2*tau*k
        frequencies = [10**(-4+i*5/1000) for i in range(1001)]
        gains = [abs(reference_speed_response(w,kp,kv,k0,tau,1.,h)) for w in frequencies]
        peak = max(range(len(gains)), key=gains.__getitem__)
        report['continuous'].append({
            'noa_midpoint_h_s':h, 'characteristic_descending':c,
            'poles':[{'real':z.real, 'imag':z.imag} for z in poles],
            'routh_margin':c[1]*c[2]-c[0]*c[3],
            'fixed_other_gains_kp_upper_exclusive':c[1]*c[2]/tau,
            'all_real_parts_negative':all(z.real<0 for z in poles),
            'reference_speed_transfer':{'nonamplification_coefficients':[c0,c2,tau*tau],
                'sufficient_nonnegative_coefficients':c0>=0 and c2>=0,
                'dc_gain':1., 'grid_max_gain':gains[peak], 'grid_peak_radps':frequencies[peak],
                'grid_radps':[frequencies[0],frequencies[-1]], 'grid_count':len(frequencies)}})
    for h, dt in ((.1,.01),(.1,.005),(.05,.005)):
        exact = zoh_matrix(kp,kv,k0,tau,1.,h)
        actual = kinematic_jacobian(model,kp,kv,k0,1.,h,dt)
        eigen_exact, eigen_actual = eigenvalues3(exact), eigenvalues3(actual)
        rho = max(abs(z) for z in eigen_actual)
        report['sampled'].append({
            'control_dt_s':h, 'integration_dt_s':dt, 'central_difference_epsilon':1e-3,
            'feedback':[kp,k0+kv,-k0*h/2], 'exact_zoh_matrix':exact,
            'actual_rk4_jacobian':actual,
            'max_matrix_error':max(abs(a-b) for ra,rb in zip(exact,actual) for a,b in zip(ra,rb)),
            'exact_zoh_eigenvalues':[{'real':z.real,'imag':z.imag} for z in eigen_exact],
            'actual_rk4_eigenvalues':[{'real':z.real,'imag':z.imag} for z in eigen_actual],
            'exact_spectral_radius':max(abs(z) for z in eigen_exact),
            'actual_spectral_radius':rho, 'equivalent_slowest_decay_per_s':math.log(rho)/h,
            'fixed_reference_locally_schur':rho<1})
    report['formation_disabled'] = {
        'spectral_radius':max(abs(z) for z in eigenvalues3(zoh_matrix(kp,kv,k0,tau,0.,.1))),
        'interpretation':'Position error is unregulated; a neutral eigenvalue is expected.'}
    report['individual_stability_counterexample'] = {
        'analytical_only_not_a_controller_parameter_change':True,
        'k0_per_s':0., 'kp_per_s2':kp, 'kv_per_s':kv, 'tau_s':tau,
        'routh_margin':kv-tau*kp, 'frequency_radps':.1,
        'reference_speed_gain':abs(reference_speed_response(.1,kp,kv,0.,tau)),
        'interpretation':'A stable single-follower error polynomial alone does not imply nonamplification.'}
    return report


def _write_json(path, data):
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')


def _hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def archive_analysis(output_root):
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    folder = Path(output_root)/f'theory_{stamp}_{uuid4().hex[:8]}'
    folder.mkdir(parents=True,exist_ok=False)
    paths = ['experiments/phase5_theory.py', 'tests/test_phase5_theory.py',
             'models/kinematic.py', 'models/vehicle.py', 'research/common.py',
             'configs/phase5.json', 'configs/phase4.json', 'configs/no_comm_main.json',
             'configs/paper_reference.json', 'configs/phase2.json', 'configs/kinematic.json',
             'noa/controller.py', 'noa/formation.py']
    for name in paths:
        target = folder/'source_snapshot'/name
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes((ROOT/name).read_bytes())
    _write_json(folder/'analysis.json',build_report())
    manifest = {'schema':'phase5_theory_archive_v1', 'python':sys.version,
                'executable':sys.executable,
                'files':{p.relative_to(folder).as_posix():_hash(p)
                         for p in sorted(folder.rglob('*')) if p.is_file()}}
    _write_json(folder/'manifest.json',manifest)
    return folder


def verify_archive(folder):
    folder = Path(folder).resolve()
    manifest = json.loads((folder/'manifest.json').read_text(encoding='utf-8'))
    required = {'analysis.json', 'source_snapshot/experiments/phase5_theory.py',
                'source_snapshot/models/kinematic.py', 'source_snapshot/models/vehicle.py',
                'source_snapshot/research/common.py'}
    if not required <= set(manifest['files']):
        raise ValueError('Incomplete theory hash manifest')
    for name, digest in manifest['files'].items():
        path = (folder/name).resolve()
        if not path.is_relative_to(folder) or not path.is_file() or _hash(path)!=digest:
            raise ValueError('Theory hash mismatch: '+name)
    frozen = folder/'source_snapshot/experiments/phase5_theory.py'
    process = subprocess.run([sys.executable,'-I','-B','-S',str(frozen),'--compute-json'],
                             capture_output=True,text=True,encoding='utf-8',timeout=30,
                             creationflags=subprocess.CREATE_NO_WINDOW if sys.platform=='win32' else 0)
    if process.returncode:
        raise ValueError('Frozen theory replay failed: '+process.stderr)
    expected = json.loads((folder/'analysis.json').read_text(encoding='utf-8'))
    actual = json.loads(process.stdout)
    if actual != expected:
        raise ValueError('Frozen theory replay report mismatch')
    return {'exact_report_match':True, 'files_verified':len(manifest['files']),
            'source_archive':str(folder), 'replay_method':'isolated_frozen_source_subprocess'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--run',action='store_true')
    group.add_argument('--replay',type=Path)
    group.add_argument('--compute-json',action='store_true')
    args = parser.parse_args()
    if args.compute_json:
        print(json.dumps(build_report(),ensure_ascii=True,allow_nan=False))
    elif args.run:
        folder = archive_analysis(ROOT/'results/phase5')
        print(json.dumps({'path':str(folder),'status':'computed'},ensure_ascii=True))
    else:
        result = verify_archive(args.replay)
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        folder = ROOT/'results/phase5'/f'theory_replay_{stamp}_{uuid4().hex[:8]}'
        folder.mkdir(parents=True,exist_ok=False)
        _write_json(folder/'replay.json',result)
        print(json.dumps({'path':str(folder),**result},ensure_ascii=True))


if __name__ == '__main__':
    main()
