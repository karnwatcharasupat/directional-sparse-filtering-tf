import tensorflow as tf
import tensorflow.keras as tfk
import fire
import soundfile as sf
from modules.dsf import LehmerMeanDSF, PowerMeanDSF


def do_bss(input_path, n_src, mode="icassp2021", proc_limit=10, **kwargs):

    # tf.debugging.enable_check_numerics()

    x, fs = sf.read(input_path, always_2d=True)

    assert x.shape[1] > 1, "Multichannel signal required"

    if mode in ["icassp2021", "lehmer"]:
        dsf = LehmerMeanDSF(x, n_src=n_src, fs=fs, r=0.5, inline_decoupling=False, **kwargs)
    elif mode in ["tsp2020", "powermean", "original"]:
        dsf = PowerMeanDSF(x, n_src=n_src, fs=fs, p=-0.5, inline_decoupling=False, **kwargs)
    else:
        raise NotImplementedError

    dsf.fit()

    y = dsf.extract(proc_limit=proc_limit)

    for s in range(n_src):
        sf.write(f"./src{s}.wav", y[s], fs)


if __name__ == "__main__":
    fire.Fire(do_bss)
