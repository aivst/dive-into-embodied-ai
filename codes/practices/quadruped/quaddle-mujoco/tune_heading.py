"""Check bounded direction-feedback gains across three contact frictions."""
from concurrent.futures import ProcessPoolExecutor
import copy
import json

from search_natural import ROOT, initialize, measure


def trial(args):
    base, kp, lateral = args
    config = copy.deepcopy(base)
    config.update(heading_kp=kp, lateral_kp=lateral)
    results = {("nominal" if mu is None else str(mu)):measure(config, seconds=16, friction=mu) for mu in (.6,None,1.)}
    valid = all(r["complete"] and r["min_up"]>.9 and r["body_contacts"] == 0
                and r["speed_m_s"]>.03 and r["max_side_m"]<.1
                and r["max_yaw_deg"]<25 for r in results.values())
    score = min(r["score"]-r["max_side_m"]-.003*r["max_yaw_deg"] for r in results.values())
    return dict(config=config, valid=valid, score=score, cases=results)


if __name__ == "__main__":
    (ROOT/"outputs").mkdir(exist_ok=True)
    base=json.loads((ROOT/"gait.json").read_text())
    jobs=[(base,kp,kx) for kp in sorted({-.5,0.,.1,.2,.4,.8,1.5,base["heading_kp"]}) for kx in [0.,1.,2.,4.]]
    records=[]
    with ProcessPoolExecutor(4,initializer=initialize) as pool:
        for r in pool.map(trial,jobs):
            records.append(r)
            print(json.dumps(dict(done=len(records),kp=r["config"]["heading_kp"],kx=r["config"]["lateral_kp"],
                                 valid=r["valid"],score=r["score"])),flush=True)
    records.sort(key=lambda r:(r["valid"],r["score"]),reverse=True)
    (ROOT/"outputs/heading_robustness_search.json").write_text(json.dumps(records,indent=2)+"\n")
