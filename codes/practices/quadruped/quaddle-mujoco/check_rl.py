"""Check environment semantics and the zero-residual physical baseline."""
import json
import numpy as np
from stable_baselines3.common.env_checker import check_env
from rl_env import QuaddleResidualEnv


def main():
    short = QuaddleResidualEnv(episode_seconds=.05, randomize=True)
    check_env(short)
    first, _ = short.reset(seed=123)
    short.step(np.zeros(4))
    second, _ = short.reset(seed=123)
    np.testing.assert_array_equal(first, second)
    for i in range(5):
        _, _, terminated, truncated, _ = short.step(np.zeros(4))
        assert not terminated and truncated == (i == 4)
    short.close()
    env = QuaddleResidualEnv()
    obs, _ = env.reset(seed=0)
    for _ in range(2000):
        obs, reward, terminated, truncated, info = env.step(np.zeros(4))
        assert np.isfinite(obs).all() and np.isfinite(reward)
        assert np.max(np.abs(env.data.ctrl)) <= 1.2
        assert not np.any(env.data.xfrc_applied) and not np.any(env.data.qfrc_applied)
        assert not terminated
    assert truncated and info['forward_m'] > 1.
    print(json.dumps({"passed": True, "observation_dim": len(obs), "zero_residual_20s_forward_m": info['forward_m'],
                      "seed_reset": True, "timeout_is_truncation": True, "joint_only": True}, indent=2))
    env.close()


if __name__ == '__main__':
    main()
