"""Compare a saved policy with zero residuals on identical held-out seeds."""
import argparse
import json
from pathlib import Path

import numpy as np
from stable_baselines3 import PPO
from stable_baselines3.common.vec_env import DummyVecEnv, VecNormalize

from rl_env import ROOT, QuaddleResidualEnv


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=Path, default=ROOT / "outputs/ppo")
    parser.add_argument("--episodes", type=int, default=10)
    parser.add_argument("--seed", type=int, default=20_000)
    parser.add_argument("--randomize", action="store_true")
    args = parser.parse_args()
    if args.episodes < 1:
        parser.error("--episodes must be positive")
    policy = PPO.load(args.model / "policy.zip", device="cpu")
    normalizer = VecNormalize.load(args.model / "vecnormalize.pkl", DummyVecEnv([QuaddleResidualEnv]))
    normalizer.training = False
    normalizer.norm_reward = False
    results = []
    env = QuaddleResidualEnv(randomize=args.randomize)
    try:
        for method in ("zero_residual", "ppo"):
            for seed in range(args.seed, args.seed + args.episodes):
                obs, _ = env.reset(seed=seed)
                total, min_up, max_lateral = 0., 1., 0.
                while True:
                    action = np.zeros(4) if method == "zero_residual" else policy.predict(normalizer.normalize_obs(obs), deterministic=True)[0]
                    obs, reward, terminated, truncated, info = env.step(action)
                    total += reward
                    min_up = min(min_up, info.get("upright", 0.))
                    max_lateral = max(max_lateral, abs(info.get("lateral_m", 0.)))
                    if terminated or truncated:
                        results.append({"method": method, "seed": seed, "return": total,
                                        "seconds": info.get("episode_seconds", env.steps * env.dt),
                                        "forward_m": info.get("forward_m", 0.), "min_upright": min_up,
                                        "max_lateral_m": max_lateral, "failed": bool(terminated)})
                        break
    finally:
        env.close(); normalizer.close()
    report = {"randomize": args.randomize, "episodes": results}
    output = args.model / ("evaluation-randomized.json" if args.randomize else "evaluation-nominal.json")
    output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
