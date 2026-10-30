# TM independent source and method review

Reviewed the production rules at SHA-256 `65142b448412325357bab0bdcdc6fa6caaa75cddef2c6a498ab4d49454441317` against Git `8ed11d90`, the T/M/TM methods, the registered protocols, screen80's saved report, and the four test adaptations plus archived-source loader. This review did not run SUMO or alter implementation, tests, or Git state. The only new file is this report.

## Finding: correct the generated comparison warning

`analysis/analyze_trials.py:362` still generates this sentence, also present in `tmp/literature_trials/screen80_analysis/report.md`:

> A rule changing regular longitudinal following also changes candidate NOA; its transform-minus-NOA comparison cannot isolate a formation-only effect.

The stated causal reason is misleading. T NOA and T transform share the same actual-front following law, so their within-candidate comparison controls that longitudinal-law change. TM's NOA is structurally the same as T's NOA because its M addition is confined to organized discretionary filling. A complete transform-versus-NOA contrast still includes other policy differences, such as cooperative merging and ordinary overtaking; that is why it cannot identify the isolated effect of one formation subrule. `analysis/review_screen48.md` already explains this distinction correctly, but generated reports retain the older wording.

Suggested replacement: “Within-candidate transform-minus-NOA controls the shared regular following law, but includes the remaining formation, cooperative-merge, and overtaking policy differences; it does not isolate one formation subrule.” This is a reporting correction and does not require changing frozen trial source or rerunning simulations.

## Source review result and interpretation limits

No substantive production correctness defect was found. A read-only AST comparison confirms that only `_following`, `_fill`, and `_decide` changed, with `_front_following` and `cf_speed` added. The shared safety functions, `_request`, merge-target and joining helpers, mandatory priority, receiving logic, and public `decide` wrapper are unchanged. The new following target uses the stated own-speed headway, and NOA explicitly retains state 0. The M cost uses public physical state and local track association without ranking by track value. Its cache is confined to one immutable observation snapshot and indexes a candidate/lane pair; the cost intentionally does not depend on a layer center, so that cache does not merge distinct cost inputs. The target rear bound is checked before aggregation, so release benefits cannot offset it.

The four changed live following assertions use the independent specified D*(v). The three historical H/P equivalence tests now exercise the hash-pinned original state-enabled controller; their historical scope is explicit, while other behavioral tests remain connected to the live rules. Existing recorded validation distinguishes the fixed-gap base with four expected failures. This review inspected that evidence; it did not rerun the test suites.

Keep the M interpretation at the level already stated in its method: `cf_speed` is a same-frame public-model counterfactual with the candidate placed laterally at its current x. It does not predict the complete joining maneuver, another driver's private state, or measured actual follower braking. The 10 m/s² threshold is the existing physical bound, not a comfort result. The saved aggregate traffic outcomes alone do not establish reduced actual braking for every affected follower.

The heldout seed batch was still running when this review was performed. No final adoption or general traffic-improvement conclusion is made here.
