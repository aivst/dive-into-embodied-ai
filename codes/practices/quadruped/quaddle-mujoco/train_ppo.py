"""Train a residual policy; a short smoke run is not evidence of learned walking."""
import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path

from stable_baselines3 import PPO
from stable_baselines3.common.callbacks import EvalCallback
from stable_baselines3.common.env_util import make_vec_env
from stable_baselines3.common.vec_env import SubprocVecEnv, VecNormalize
import torch

from rl_env import ROOT, QuaddleResidualEnv


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--steps", type=int, default=1_000_000)
    parser.add_argument("--envs", type=int, default=4)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--randomize", action="store_true")
    parser.add_argument("--smoke", action="store_true", help="Small network/update batch for verifying the pipeline")
    parser.add_argument("--output", type=Path, default=ROOT / "outputs/ppo")
    args = parser.parse_args()
    if args.steps < 1 or args.envs < 1:
        parser.error("--steps and --envs must be positive")
    args.output.mkdir(parents=True, exist_ok=True)
    torch.set_num_threads(1)
    env = make_vec_env(QuaddleResidualEnv, n_envs=args.envs, seed=args.seed,
                       env_kwargs={"randomize": args.randomize},
                       vec_env_cls=SubprocVecEnv if args.envs > 1 else None)
    env = VecNormalize(env, norm_obs=True, norm_reward=False, clip_obs=10.)
    # Fixed nominal evaluation seeds are separate from training seeds. An
    # additional randomized held-out evaluation is run explicitly by evaluate_ppo.py.
    eval_env = VecNormalize(make_vec_env(QuaddleResidualEnv, seed=10_000), training=False, norm_reward=False)
    callback = EvalCallback(eval_env, eval_freq=max(1, 20_000 // args.envs), n_eval_episodes=5,
                            log_path=str(args.output / "evaluation"), deterministic=True)
    model = PPO("MlpPolicy", env, device="cpu", seed=args.seed, verbose=1,
                n_steps=128 if args.smoke else 1024, batch_size=64 if args.smoke else 256,
                n_epochs=2 if args.smoke else 10, learning_rate=3e-4, gamma=.995,
                gae_lambda=.95, clip_range=.2, ent_coef=.001,
                policy_kwargs={"net_arch": [64, 64], "log_std_init": -1.5})
    try:
        model.learn(total_timesteps=args.steps, callback=callback)
        # Save policy and observation statistics together; never pair a best
        # checkpoint with normalization from a different training iteration.
        model.save(args.output / "policy")
        env.save(args.output / "vecnormalize.pkl")
        metadata = {"seed": args.seed, "requested_steps": args.steps, "actual_steps": model.num_timesteps,
                    "randomize": args.randomize, "smoke_only": args.smoke,
                    "model_sha256": hashlib.sha256((ROOT / "models/scene.xml").read_bytes()).hexdigest(),
                    "gait_sha256": hashlib.sha256((ROOT / "gait.json").read_bytes()).hexdigest(),
                    "observation_dim": 32, "action_dim": 4, "control_hz": 100,
                    "residual_scale_rad": .12,
                    "versions": {name: importlib.metadata.version(name) for name in ("mujoco", "gymnasium", "stable-baselines3", "torch", "numpy")}}
        (args.output / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")
    finally:
        env.close(); eval_env.close()


if __name__ == "__main__":
    main()
