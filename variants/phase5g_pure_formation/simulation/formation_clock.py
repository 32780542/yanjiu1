"""Phase5 policy hooks on the unchanged freeze/decide/integrate/commit protocol."""
import math
from noa.formation import FormationMemory, decide
from simulation.noa_clock import NoaClock


class FormationClock(NoaClock):
    def _check_features(self):
        if self.p['communication_enabled'] or self.policy.get('communication_enabled', False):
            raise ValueError('Formation requires communication off')
        if self.p['formation_enabled'] != self.policy.get('formation_enabled', False):
            raise ValueError('Formation clock and policy switches must agree')
        if not math.isclose(self.p['control_sync_dt_s'], self.policy['control_sync_dt_s'],
                            abs_tol=1e-12, rel_tol=0.):
            raise ValueError('Formation physical/control policy periods must agree')

    def _initial_memory(self):
        return FormationMemory((), 'CRUISE') if self.p['formation_enabled'] else super()._initial_memory()

    def _decide(self, control):
        return decide(control, self.policy)
